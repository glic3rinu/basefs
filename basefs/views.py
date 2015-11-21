import binascii
import copy
import os
import sys
from collections import defaultdict

import bsdiff4

from basefs import exceptions
from basefs.utils import Candidate, issubdir


class ViewNode:
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
        return '<%s %s %s %s>' % (self.entry.action, self.entry.name, content[:32], self.entry.hash)
    
    def __init__(self, entry, path, childs=None, parent=None):
        self.entry = entry
        self.path = path
        self.childs = childs or []
        self.parent = parent
        self.perm = None
    
    @property
    def content(self):
        if not hasattr(self, '_content'):
            content = b""
            ancestor = self.entry
            ancestors = [ancestor]
            while True:
                ancestor = ancestor.parent
                if ancestor is None or ancestor.action != self.entry.action:
                    break
                ancestors.insert(0, ancestor)
            for ancestor in ancestors:
                ancestor_content = ancestor.get_content()
                if not ancestor_content:
                    content = ancestor_content
                else:
                    content = bsdiff4.patch(content, ancestor_content)
            self._content = content
        return self._content
    
    @property
    def is_file(self):
        return self.entry.action == self.entry.WRITE
    
    @property
    def is_dir(self):
        return self.entry.action == self.entry.MKDIR
    
    @property
    def is_permission(self):
        return self.entry.action in (self.entry.GRANT, self.entry.REVOKE)
    
    @property
    def is_link(self):
        return self.entry.action == self.entry.LINK
    
    @property
    def is_symlink(self):
        return self.entry.action == self.entry.SLINK


class View:
    def __init__(self, log, *keys):
        self.log = log
        self.keys = {key.fingerprint: key for key in keys}
        self.granted_paths = {}
    
    def get(self, path):
        return self.paths[path]
    
    def build(self, partial=None):
        # TODO partial support
        if not self.log.root_key:
            raise RuntimeError("Log %s not loaded" % self.log.logpath)
        root_key = self.log.root_key.read_key()
        root_key.upper_path = os.sep
        keys = {
            root_key.fingerprint: root_key
        }
        self.granted_paths.clear()
        __, __, paths, root = self.rec_build(self.log.root, keys, os.sep)
        self.paths = paths
        self.root = root
        return self.root
    
    def rec_build(self, entry, keys, path):
        if entry.action != entry.MKDIR:
            raise exceptions.IntegrityError("WTF are you calling rec_build on?")
        # Lookup for delete+mkdir pattern
        score, state = entry.get_branch_state(keys)
        if state == [None]*4:
            return
        path = os.path.join(path, entry.name)
        node = ViewNode(state, path)
        paths = {
            path: node
        }
        if state.action == entry.DELETE:
            return score, state, paths, node
        childs = defaultdict(list)
        perms = []
        for child in entry.childs:
            if child.action in (entry.GRANT, entry.REVOKE):
                perms.append(child)
            # same path branch has been already inspected
            elif entry.name != child.name:
                childs[child.name].append(child)
        if perms:
            perm_score, perm_state = entry.get_branch_state(keys, *perms, path=path)
            if perm_state:
                score += perm_score
                perm_node = ViewNode(perm_state, path)
                node.perm = perm_node
                node.childs.append(perm_node)
                perm_node.parent = node
                state_keys = perm_state.branch_keys
                self.update_granted_paths(path, state_keys)
                for k, v in state_keys.items():
                    if k not in keys:
#                        v.upper_path = entry.path
                        keys[k] = v
        for name, childs in childs.items():
            selected = None
            for child in childs:
                child_score, child_state = entry.get_branch_state(keys, child)
                child_path = os.path.join(path, child.name)
                child_node = ViewNode(child_state, child_path)
                child_paths = {
                    child_path: child_node
                }
                if child_state:
                    if child_state.action == entry.MKDIR:
                        # Add all of the directory score
                        # TODO because we are calling on child_state we miss the possible scores on the non-active branches
                        mkdir_score, child_state, mkdir_paths, child_node = self.rec_build(child_state, copy.copy(keys), path)
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
                try:
                    granted_paths = self.granted_paths[fingerprint]
                except KeyError:
                    granted_paths = set()
                    self.granted_paths[fingerprint] = granted_paths
                for granted_path in granted_paths:
                    if issubdir(path, granted_path):
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
                elif issubdir(path, granted_path):
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
            if node.perm and issubdir(npath, path):
                branch = []
                parent = node.perm
                while parent.is_permission:
                    branch.insert(0, parent)
                    parent = parent.parent
                keys = {}
                for node in branch:
                    key = node.entry.read_key()
                    if node.entry.action == node.entry.REVOKE:
                        keys.pop(key.fingerprint)
                    else:
                        keys[key.fingerprint] = key
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
    
    def do_action(self, parent, action, path, name, commit=True, **kwargs):
        key = self.get_key(path)
        if key is None:
            raise exceptions.PermissionDenied(path)
        entry = action(parent.entry, name, key, commit=commit, **kwargs)
        node = ViewNode(entry, path)
        if node.is_permission:
            self.paths[path].perm = node
        else:
            self.paths[path] = node
        if not parent.is_permission and parent.entry.name == name and parent.parent:
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
        name = path.split(os.sep)[-1]
        return self.do_action(parent, self.log.mkdir, path, name, commit=commit)
    
    def write(self, path, content, commit=True):
        path = os.path.normpath(path)
        try:
            parent = self.get(path)
        except exceptions.DoesNotExist:
            parent = self.get(os.path.dirname(path))
        content = bsdiff4.diff(parent.content, content)
        name = path.split(os.sep)[-1]
        return self.do_action(parent, self.log.write, path, name, attachment=content, commit=commit)
    
    def rec_delete_paths(self, node):
        self.paths.pop(node.path)
        for child in node.childs:
            self.rec_delete_paths(child)
        node.childs = []
    
    def delete(self, path, commit=True):
        path = os.path.normpath(path)
        parent = self.get(path)
        if parent.entry.action == parent.entry.MKDIR:
            for child in parent.childs:
                self.rec_delete_paths(child)
        name = path.split(os.sep)[-1]
        return self.do_action(parent, self.log.delete, path, name, commit=commit)
    
    def rec_diff(self, node_a, node_b, diffs):
        if node_a.entry != node_b.entry:
            diffs.append((node_a.entry, node_b.entry))
        b_childs = {child.path: child for child in node_b.childs if not child.is_permission}
        for a_child in node_a.childs:
            if not a_child.is_permission:
                b_child = b_childs.pop(a_child.path)
                self.rec_diff(a_child, b_child, diffs)
        if b_childs:
            raise KeyError
        return diffs
    
    def grant(self, path, name, key=None):
        path = os.path.normpath(path)
        parent = self.get(path)
        if parent.perm:
            parent = parent.perm
        if not isinstance(name, str):
            raise ValueError("Name '%s' is not string" % name)
        node = self.do_action(parent, self.log.grant, path, name, content=key, commit=False)
        # Rebuild view in order to lookup for changes caused by granting permissions
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
        key = node.entry.read_key()
        self.update_granted_paths(path, {
            key.fingerprint: key
        })
        return node
    
    def rec_maintain_current_state(self, node, fingerprint, confirm=False):
        entry = node.entry
        if confirm or entry.fingerprint == fingerprint:
            confirm = False
            if entry.action == entry.DELETE:
                self.do_action(node, self.log.delete, node.path, entry.name)
            elif entry.action == entry.WRITE:
                self.do_action(node, self.log.write, node.path, entry.name, content=entry.content)
            elif entry.action == entry.MKDIR:
                if not node.childs:
                    self.do_action(node, self.log.mkdir, node.path, entry.name)
                else:
                    confirm = True
        for child in node.childs:
            self.rec_maintain_current_state(child, fingerprint, confirm)
    
    def revoke(self, path, name):
        fingerprint = self.log.get_key(name).fingerprint
        keypaths = self.get_keys(path)[fingerprint]
        if not keypaths:
            raise KeyError("%s fingerprint not present on %s" % (fingerprint, path))
        # Revoke key from keypaths
        for path in keypaths:
            parent = self.get(path).perm
            ret = self.do_action(parent, self.log.revoke, path, name)
        
        # Get Higher paths
        selected = set()
        for path in keypaths:
            path = os.path.dirname(path)  # remove .keys
            for spath in selected:
                if issubdir(path, spath):
                    selected.remove(spath)
                    selected.add(path)
            if path not in selected:
                selected.add(path)
        # Confirm valid state for all affected nodes
        for path in selected:
            print('p', path)
            node = self.get(path)
            print(node, fingerprint)
            self.rec_maintain_current_state(node, fingerprint)
        return ret
