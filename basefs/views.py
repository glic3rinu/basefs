import copy
import os
from collections import defaultdict

from basefs import exceptions
from basefs.utils import Candidate, is_subdir


class ViewNode(object):
    def __str__(self, indent=''):
        ret = repr(self) + '\n'
        if not self.childs:
            return ret
        for child in self.childs[:-1]:
            ret += indent + '  ├─'
            ret += child.__str__(indent + '  │ ')
        ret += indent + '  └─'
        ret += self.childs[-1].__str__(indent + '    ')
        return ret
    
    def __repr__(self):
        return '<%s %s %s>' % (self.entry.action, self.entry.path, self.entry.content.replace('\n', '\\n')[:32])
    
    def __init__(self, entry, childs=None):
        self.entry = entry
        self.childs = childs or []
    
    def mkdir(self, path):
        self.entry.mkdir(path)
        self.build(self.log)
    
    def write(self, content):
        parent = getattr(self, 'future_parent', self)
        parent.entry.write(self.entry.path, content)
        parent.build(parent.log)
    
    def create(self, path):
        entry = type(self.log)(self.entry, LogEntry.WRITE, path, '')
        entry.ctime = int(time.time())
        entry.time = entry.ctime
        node = View(entry)
        node.future_parent = self
        self.paths[path] = node


class View(object):
    def __init__(self, log, *keys):
        self.log = log
        self.keys = {key.fingerprint: key for key in keys}
        self.granted_paths = defaultdict(set)
    
    def build(self):
        if not self.log.root_keys:
            raise RuntimeError("Log %s not loaded" % self.log.logpath)
        keys = self.log.root_keys.read_keys()
        __, __, paths, root = self.rec_build(self.log.root, keys)
        self.paths = paths
        self.root = root
        return self.root
    
    def get(self, path):
        return self.paths[path]
    
    def rec_build(self, entry, keys):
        # TODO copy.copy instead of deepcopy
        if entry.action != entry.MKDIR:
            raise exceptions.IntegrityError("WTF are you calling rec_build on?")
        # Lookup for delete+mkdir pattern
        score, state = entry.get_branch_state(keys)
        if state == [None]*4:
            return
        node = ViewNode(state)
        paths = {
            entry.path: node
        }
        if state.action == entry.DELETE:
            return score, state, paths, node
        childs = defaultdict(list)
        for child in entry.childs:
            # same path branch has been already inspected
            if entry.path != child.path:
                childs[child.path].append(child)
        keys_path = os.path.join(entry.path, '.keys')
        key_entries = childs.pop(keys_path, None)
        if key_entries:
            # lookup for keys
            key_score, key_state = entry.get_branch_state(copy.copy(keys), *key_entries)
            if key_state:
                score += key_score
                key_node = ViewNode(key_state)
                node.childs.append(key_node)
                paths[key_state.path] = key_node
                keys = key_state.read_keys()
                self.update_granted_paths(entry.path, keys)
                keys.update(keys)
        for path, childs in childs.items():
            selected = None
            for child in childs:
                # MKDIR /hola, MKDIR /hola, WRITE /hola
                child_score, child_state = entry.get_branch_state(copy.copy(keys), *childs)
                child_node = ViewNode(child_state)
                child_paths = {
                    path: child_node
                }
                if child_state:
                    if child_state.action == entry.MKDIR:
                        child_score, child_state, child_paths, child_node = self.rec_build(child_state, copy.copy(keys))
                    candidate = Candidate(score=child_score, entry=child)
                    if not selected or candidate > selected:
                        selected = candidate
                        selected.node = child_node
                        selected.paths = child_paths
            if selected:
                node.childs.append(selected.node)
                score = selected.score + score if score else selected.score
                paths.update(selected.paths)
        return score, state, paths, node
    
    def update_granted_paths(self, path, keys):
        for fingerprint, key in keys.items():
            if fingerprint in self.keys:
                granted_paths = self.granted_paths[fingerprint]
                for granted_path in granted_paths:
                    if path != granted_path and is_subdir(path, granted_path):
                        granted_paths.remove(granted_path)
                        granted_paths.add(path)
                        break
                else:
                    granted_paths.add(path)
    
    def get_key(self, path):
        """ path is granted by any self.keys """
        selected = None
        selected_min_path = None
        for fingerprint, granted_paths in self.granted_paths.items():
            min_path = None
            for granted_path in granted_paths:
                if granted_path == '/':
                    return self.keys[fingerprint]
                elif is_subdir(path, granted_path):
                    if min_path is None or min_path > len(granted_path.split(os.sep)):
                        min_path = len(granted_path.split(os.sep))
            if min_path is not None and (selected_min_path is None or min_path < selected_min_path):
                selected = fingerprint
                selected_min_path = min_path
        if selected:
            return self.keys[selected]
        return None
    
    def get_keys(self, path='/', by_dir=False):
        result = defaultdict(set)
        for npath, node in self.paths.items():
            if npath.endswith('/.keys') and is_subdir(npath, path):
                keys = node.entry.read_keys()
                for fingerprint, key in keys.items():
                    if by_dir:
                        result[npath].add(fingerprint)
                    else:
                        result[fingerprint].add(npath)
        return result
    
    def get(self, path):
        try:
            node = self.paths[path]
        except KeyError:
            raise exceptions.DoesNotExist(path)
        return node
    
    def do_action(self, parent, action, path, *content):
        key = self.get_key(path)
        if key is None:
            raise exceptions.PermissionDenied(path)
        args = content + (key,)
        entry = action(parent.entry, path, *args)
        node = ViewNode(entry)
        self.paths[path] = node
        # TODO grandparent
        parent.childs.append(node)
        return node
    
    def mkdir(self, path):
        path = os.path.normpath(path)
        parent = self.paths.get(path)
        if parent:
            if parent.entry.action != parent.entry.DELETE:
                raise exceptions.Exists(path)
        else:
            parent = self.get(os.path.dirname(path))
        self.do_action(parent, self.log.mkdir, path)
    
    def write(self, path, content):
        path = os.path.normpath(path)
        try:
            parent = self.get(path)
        except exceptions.DoesNotExist:
            parent = self.get(os.path.dirname(path))
        self.do_action(parent, self.log.write, path, content)
    
    def rec_delete_paths(self, node):
        self.paths.pop(node.entry.path)
        for child in node.childs:
            self.rec_delete_paths(child)
        node.childs = []
    
    def delete(self, path):
        path = os.path.normpath(path)
        parent = self.get(path)
        if parent.entry.action == parent.entry.MKDIR:
            for child in parent.childs:
                self.rec_delete_paths(child)
        node = self.do_action(parent, self.log.delete, path)
    
    def grant(self, path, key):
        path = os.path.normpath(path)
        keys_path = os.path.join(path, '.keys')
        content = key.oneliner() + '\n'
        try:
            parent = self.get(keys_path)
        except exceptions.DoesNotExist:
            parent = self.get(path)
        else:
            content = parent.entry.content + content
        self.do_action(parent, self.log.write, keys_path, content)
    
    def revoke(self, path, fingerprint):
        keypaths = self.get_keys(path)[fingerprint]
        # Remove key from keypaths
        for path in keypaths:
            parent = self.get(path)
            keys = parent.entry.read_keys()
            content = ''
            for key in keys:
                if key.fingerprint != fingerprint:
                    content += key.oneliner() + '\n'
            self.do_action(parent, self.log.write, path, content)
        
        # Get Higher paths
        selected = set()
        for path in keypaths:
            path = os.path.dirname(path)  # remove .keys
            for spath in selected:
                if is_subdir(path, spath):
                    selected.remove(spath)
                    selected.add(path)
            if path not in selected:
                selected.add(path)
        # Confirm valid state for all affected nodes
        # TODO rec revoke from node instead of this shit
        for path, node in self.path.items():
            for spath in selected:
                if is_subdir(path, spath) and path not in keypaths:
                    break
            else:
                continue
            if node.entry.fingerprint == fingerprint:
                if node.entry.action == LogEntry.DELETE:
                    self.do_action(node, self.log.delete, path)
                elif node.entry.action == LogEntry.WRITE:
                    self.do_action(node, self.log.write, path, node.entry.content)
                elif node.entry.action == LogEntry.MKDIR:
                    pass
                    # TODO if mkdir: lookup also for childs
