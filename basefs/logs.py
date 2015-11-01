import base64
import binascii
import copy
import hashlib
import itertools
#import lzma vs zlib
import os
import re
import time
import zlib
from collections import defaultdict

from .keys import Key
from .exceptions import ValidationError
from .utils import Candidate


class Log(object):
    root = None
    root_keys = None
    root_cluster = None
    
    def __str__(self):
        return self.print_tree()
    
    def __repr__(self):
        return self.logpath
    
    def __init__(self, logpath):
        self.logpath = logpath
        self.entries = {}
        self.entries_by_parent = defaultdict(list)
    
    def print_tree(self, entry=None, indent='', view=None, bold=False):
        if entry is None:
            entry = self.root
        ret = repr(entry) + '\n'
        if view:
            node = view.get(entry.path)
            if node and node.entry.hash == entry.hash:
                ret = '*' + ret
                if bold:
                    ret = '\033[1m\033[92m' + ret + '\033[0m'
        childs = self.entries_by_parent[entry.hash]
        if not childs:
            return ret
        for child in childs[:-1]:
            ret += indent + '  ├─'
            ret += self.print_tree(child, indent + '  │ ', view, bold)
        child = childs[-1]
        ret += indent + '  └─'
        ret += self.print_tree(child, indent + '    ', view, bold)
        return ret
    
    def encode(self, entry):
        content = entry.content
        if content:
            content = zlib.compress(entry.content.encode())
            content = binascii.b2a_base64(content).decode().rstrip()
        signature = binascii.b2a_base64(entry.signature).decode().rstrip()
        return ' '.join(map(str, (entry.hash, entry.parent_hash, entry.time, entry.fingerprint, entry.action, entry.path, content, signature)))
    
    def decode(self, line):
        hash, parent_hash, time, fingerprint, action, path, content, signature = line.split(' ')
        if content:
            content = binascii.a2b_base64(content.encode())
            content = zlib.decompress(content).decode()
        signature = binascii.a2b_base64(signature.encode())
        time = int(time)
        return LogEntry(self, parent_hash, action, path, content,
            time=time, fingerprint=fingerprint, signature=signature)
    
    def load(self):
        """ loads logfile """
        self.entries_by_parent.clear()
        self.entries = {}
        root = None
        root_keys = None
        root_cluster = None
        with open(self.logpath, 'r') as log:
            # Read all log entries
            for line in log.readlines():
                entry = self.decode(line)
                try:
                    self.validate(entry)
                except KeyError:
                    # missing key
                    pass
                    # TODO readkeys now???
                # 0: root, 1: .keys, 2: .cluster
                if not self.root:
                    self.root = entry
                elif not self.root_keys:
                    self.root_keys = entry
                elif not self.root_cluster:
                    self.root_cluster = entry
                self.entries[entry.hash] = entry
                self.entries_by_parent[entry.parent_hash].append(entry)
        # Build FS hierarchy
        for parent_hash, childs in self.entries_by_parent.items():
            if parent_hash == LogEntry.ROOT_PARENT_HASH:
                continue
            parent = self.entries[parent_hash]
            for child in childs:
                child.parent = parent
#            parent.childs = childs
        return self.root
    
    def bootstrap(self, keys, ips):
        root_key = keys[0]
        root = self.mkdir(parent=None, path='/', key=root_key)
        keys = '\n'.join((key.oneliner() for key in keys)) + '\n'
        self.write(parent=root, path='/.keys', content=keys, key=root_key)
        ips = '\n'.join(ips) + '\n'
        self.write(parent=root, path='/.cluster', content=ips, key=root_key)
    
    def do_action(self, parent, action, path, key, *content):
        path = os.path.normpath(path)
        entry = LogEntry(self, parent, action, path, *content)
        entry.sign(key)
        self.validate(entry)
        self.entries[entry.hash] = entry
        self.entries_by_parent[entry.parent_hash].append(entry)
        self.save(entry)
        return entry
    
    def validate(self, entry):
        # TODO
#        key = self.keys[entry.fingerprint]
#        entry.verify(key)
        if entry.hash in self.entries:
            raise self.IntegrityError("%s already exists" % entry.hash)
        entry.clean()
    
    def mkdir(self, parent, path, key):
        return self.do_action(parent, LogEntry.MKDIR, path, key)
    
    def write(self, parent, path, content, key):
        return self.do_action(parent, LogEntry.WRITE, path, key, content)
    
    def delete(self, parent, path, key):
        return self.do_action(parent, LogEntry.DELETE, path, key)
    
    def save(self, entry):
        with open(self.logpath, 'a') as logfile:
            logfile.write(self.encode(entry) + '\n')


class LogEntry(object):
    MKDIR = 'MKDIR'
    WRITE = 'WRITE'
    DELETE = 'DELETE'
    ACTIONS = set((MKDIR, WRITE, DELETE))
    ROOT_PARENT_HASH = '0'*32
    
    def __str__(self):
        return '{%s %s %s %s}' % (self.action, self.path, self.hash, self.content.replace('\n', '\\n')[:32])
    
    def __repr__(self):
        return str(self)
    
    def __init__(self, log, parent, action, path, *content, **kwargs):
        self.time = kwargs.get('time') or int(time.time())
        if isinstance(parent, LogEntry):
            self.parent_hash = parent.hash
            self.parent = parent
        else:
            self.parent_hash = parent or self.ROOT_PARENT_HASH
        self.action = action
        self.path = path
        self.log = log
        self.hash = kwargs.get('hash')
        self.fingerprint = kwargs.get('fingerprint')
        self.signature = kwargs.get('signature')
        self.content = '' if not content else content[0]
        if not self.hash and self.signature:
            self.hash = self.get_hash()
    
    @property
    def childs(self):
        return self.log.entries_by_parent[self.hash]
    
    def clean(self):
        """ cleans log entry """
        self.path = os.path.normpath(self.path)
        if self.action not in self.ACTIONS:
            raise ValidationError("'%s' not a valid action type" % self.action)
        if os.path.basename(self.path) == '.keys':
            if self.action is self.MKDIR:
                raise ValidationError(".keys can not be a directory.")
            elif self.action is self.WRITE:
                # Validates keys
                self.read_keys()
        if not re.match(r'^[0-9a-f]{32}$', self.parent_hash):
            raise ValidationError("%s not a valid md5 hash" % self.parent_hash)
    
    def get_valid_key(self, keys, last_keys):
        for fingerprint, key in itertools.chain(keys.items(), last_keys.items()):
            if self.fingerprint == fingerprint:
                return key
    
    def rec_get_branch_state(self, score, path, keys, last):
        """ gets last blockchain entry """
        last_keys = {}
        # Needed for processing .key chain
        if last and os.path.basename(last.path) == '.keys':
            last_keys = last.read_keys()
        key = self.get_valid_key(keys, last_keys)
        if key:
            # Is valid
            # FIXME invalid keys folllowed by a valid one also should score!
            score = Score(key) if score is None else (Score(key) + score)
            last = self
        selected = None
        for child in self.childs:
            # needed for processing mkdir branches
            if child.path == path:
                child_score, child_last = child.rec_get_branch_state(score, path, keys, last)
                if child_last is not None:
                    candidate = Candidate(score=child_score, entry=child)
                    if not selected or candidate > selected:
                        selected = candidate
                        selected.last = child_last
        if selected:
            return score, selected.last
        return score, last
    
    def get_branch_state(self, keys, *entries):
        if entries:
            if len(entries) == 1:
                entry = entries[0]
            else:
                entry = copy.copy(entries[0])
                entry.childs = entries
                entry.is_mocked = True
        else:
            entry = self
        score, last = entry.rec_get_branch_state(Score(), entry.path, keys, None)
        if getattr(last, 'is_mocked', False):
            return Score(), None
        last.ctime = entry.time
        return score, last
    
    def read_keys(self):
        keys = {}
        for line in self.content.splitlines():
            line = line.strip()
            line = '-----BEGIN EC PRIVATE KEY-----\n' + line + '-----END EC PRIVATE KEY-----'
            key = Key.from_pem(line)
            # TODO keys are singletones.....
            key.add_path(self.path)
            keys[key.fingerprint] = key
        return keys
    
    def get_hash(self):
        line = ' '.join(map(str, (self.parent_hash, self.time, self.action, self.path, self.content, self.fingerprint)))
        return hashlib.md5(line.encode()).hexdigest()
    
    def sign(self, key):
        self.fingerprint = key.fingerprint
        self.hash = self.get_hash()
        self.signature = key.sign(self.hash.encode())
    
    def verify(self, key):
        if not self.hash:
            self.hash = self.get_hash()
        vk = key.get_verifying_key()
        if not vk.verify(self.signature, self.hash):
            raise ValidationError("Failed hash verification %s %s" % (self.hash, self.fingerprint))


# TODO count upper-class keys first (needed for key revokation)
class Score(object):
    """ allways growing datastructure """
    
    def __init__(self, *keys):
        self.keys = set()
        self.weight = 0
        self.length = 0
        self._add_keys(keys)
    
    def _add_keys(self, keys):
        path_length = lambda p: len(str.split(p, os.sep))
        for key in keys:
            if key not in self.keys:
                self.keys.add(key)
                self.length += 1
                self.weight += min(map(path_length, key.paths))
    
    def __len__(self):
        return self.length
    
    def __add__(self, score):
        self._add_keys(score.keys)
        return self
    
    def __gt__(self, score):
        return len(self) > len(score) or (len(self) == len(score) and self.weight < score.weight)
    
    def __lt__(self, score):
        return len(self) < len(score) or (len(self) == len(score) and self.weight > score.weight)
    
    def __eq__(self, score):
        return len(self) == len(score) and self.weight == score.weight
