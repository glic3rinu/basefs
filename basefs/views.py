import copy
import os
import sys
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
        content = self.entry.content.replace('\n', '\\n')
        return '<%s %s %s %s>' % (self.entry.action, self.entry.path, content[:32], self.entry.hash)
    
    def __init__(self, entry, childs=None, parent=None):
        self.entry = entry
        self.childs = childs or []
        self.parent = parent


class View(object):
    def __init__(self, log, *keys):
        self.log = log
        self.keys = {key.fingerprint: key for key in keys}
        self.granted_paths = defaultdict(set)
    
    def get(self, path):
        return self.paths[path]
    
    def build(self, partial=None):
        # TODO partial support
        if not self.log.root_keys:
            raise RuntimeError("Log %s not loaded" % self.log.logpath)
        keys = self.log.root_keys.read_keys()
        self.granted_paths.clear()
        for key in keys.values():
            key.upper_path = os.sep
        __, __, paths, root = self.rec_build(self.log.root, keys)
        self.paths = paths
        self.root = root
        return self.root
    
    def rec_build(self, entry, keys,):
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
            key_score, key_state = entry.get_branch_state(keys, *key_entries)
            if key_state:
                score += key_score
                key_node = ViewNode(key_state)
                node.childs.append(key_node)
                key_node.parent = node
                paths[key_state.path] = key_node
                state_keys = key_state.read_keys()
                self.update_granted_paths(entry.path, state_keys)
                for k, v in state_keys.items():
                    if k not in keys:
                        v.upper_path = entry.path
                        keys[k] = v
        for path, childs in childs.items():
            selected = None
            for child in childs:
                child_score, child_state = entry.get_branch_state(keys, child)
                child_node = ViewNode(child_state)
                child_paths = {
                    path: child_node
                }
                if child_state:
                    if child_state.action == entry.MKDIR:
                        # Add all of the directory score
                        # TODO because we are calling on child_state we miss the possible scores on the non-active branches
                        mkdir_score, child_state, mkdir_paths, child_node = self.rec_build(child_state, copy.copy(keys))
                        child_score += mkdir_score
                        child_paths.update(mkdir_paths)
                    candidate = Candidate(score=child_score, entry=child)
                    if not selected or candidate > selected:
                        selected = candidate
                        selected.node = child_node
                        selected.paths = child_paths
            if selected:
                selected.node.parent = node
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
        path = os.path.normpath(path)
        selected = None
        selected_min_path = sys.maxsize
        for fingerprint, granted_paths in self.granted_paths.items():
            min_path = sys.maxsize
            for granted_path in granted_paths:
                if granted_path == '/':
                    return self.keys[fingerprint]
                elif is_subdir(path, granted_path):
                    min_path = min(min_path, granted_path.count(os.sep))
            if min_path < selected_min_path:
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
    
    def do_action(self, parent, action, path, *content, commit=True):
        key = self.get_key(path)
        if key is None:
            raise exceptions.PermissionDenied(path)
        args = content + (key,)
        entry = action(parent.entry, path, *args, commit=commit)
        node = ViewNode(entry)
        self.paths[path] = node
        if parent.entry.path == path and parent.parent:
            parent.parent.childs.remove(parent)
            parent.parent.childs.append(node)
            node.parent = parent.parent
        else:
            parent.childs.append(node)
            node.parent = parent
        return node
    
    def mkdir(self, path, commit=True):
        path = os.path.normpath(path)
        parent = self.paths.get(path)
        if parent:
            if parent.entry.action != parent.entry.DELETE:
                raise exceptions.Exists(path)
        else:
            parent = self.get(os.path.dirname(path))
        return self.do_action(parent, self.log.mkdir, path, commit=commit)
    
    def write(self, path, content, commit=True):
        path = os.path.normpath(path)
        try:
            parent = self.get(path)
        except exceptions.DoesNotExist:
            parent = self.get(os.path.dirname(path))
        return self.do_action(parent, self.log.write, path, content, commit=commit)
    
    def rec_delete_paths(self, node):
        self.paths.pop(node.entry.path)
        for child in node.childs:
            self.rec_delete_paths(child)
        node.childs = []
    
    def delete(self, path, commit=True):
        path = os.path.normpath(path)
        parent = self.get(path)
        if parent.entry.action == parent.entry.MKDIR:
            for child in parent.childs:
                self.rec_delete_paths(child)
        return self.do_action(parent, self.log.delete, path, commit=commit)
    
    def rec_diff(self, node_a, node_b, diffs):
        if node_a.entry != node_b.entry:
            diffs.append((node_a.entry, node_b.entry))
        b_childs = {child.entry.path: child for child in node_b.childs}
        for a_child in node_a.childs:
            b_child = b_childs.pop(a_child.entry.path)
            self.rec_diff(a_child, b_child, diffs)
        if b_childs:
            raise KeyError
        return diffs
    
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
        node = self.do_action(parent, self.log.write, keys_path, content, commit=False)
        post = type(self)(self.log, *self.keys.values())
        post.build()
        for pre_entry, __ in self.rec_diff(self.root, post.root, []):
            if pre_entry.action in (pre_entry.DELETE, pre_entry.MKDIR):
                getattr(post, pre_entry.action.lower())(pre_entry.path)
            else:
                getattr(post, pre_entry.action.lower())(pre_entry.path, pre_entry.content)
        node.entry.sign()
        node.entry.save()
        self.paths = post.paths
        self.root = post.root
        return self.get(keys_path)
    
    def rec_maintain_current_state(self, node, fingerprint, confirm=False):
        entry = node.entry
        if confirm or entry.fingerprint == fingerprint:
            confirm = False
            if entry.action == entry.DELETE:
                self.do_action(node, self.log.delete, entry.path)
            elif entry.action == entry.WRITE:
                self.do_action(node, self.log.write, entry.path, entry.content)
            elif entry.action == entry.MKDIR:
                if not node.childs:
                    self.do_action(node, self.log.mkdir, entry.path)
                else:
                    confirm = True
        for child in node.childs:
            self.rec_maintain_current_state(child, fingerprint, confirm)
    
    def revoke(self, path, fingerprint):
        fingerprint = getattr(fingerprint, 'fingerprint', fingerprint)
        keypaths = self.get_keys(path)[fingerprint]
        if not keypaths:
            raise KeyError("%s fingerprint not present on %s" % (fingerprint, path))
        # Remove key from keypaths
        for path in keypaths:
            parent = self.get(path)
            keys = parent.entry.read_keys()
            content = ''
            for key in keys.values():
                if key.fingerprint != fingerprint:
                    content += key.oneliner() + '\n'
            ret = self.do_action(parent, self.log.write, path, content)
        
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
        for path in selected:
            node = self.get(path)
            self.rec_maintain_current_state(node, fingerprint)
        return ret
