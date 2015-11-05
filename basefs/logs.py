import base64
import binascii
import copy
import hashlib
import itertools
#import lzma vs zlib
import os
import re
import sys
import time
import zlib
from collections import defaultdict

from .keys import Key
from .exceptions import ValidationError, IntegrityError
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
        self.keys = {}
        self.loaded = 0
        self.entries_by_parent = defaultdict(list)
    
    def print_tree(self, entry=None, indent='', view=None, color=False, ascii=False):
        if entry is None:
            entry = self.root
        ret = repr(entry) + '\n'
        if view:
            node = view.get(entry.path)
            if node and node.entry.hash == entry.hash:
                ret = '*' + ret
                if color:
                    ret = '\033[1m\033[92m' + ret + '\033[0m'
        childs = self.entries_by_parent[entry.hash]
        if not childs:
            return ret
        for child in childs[:-1]:
            sep = '  |-' if ascii else '  ├─'
            ret += indent + sep
            sep = '  | ' if ascii else '  │ '
            ret += self.print_tree(child, indent+sep, view, color, ascii)
        child = childs[-1]
        sep = '  `-' if ascii else '  └─'
        ret += indent + sep
        ret += self.print_tree(child, indent + '    ', view, color, ascii)
        return ret
    
    def encode(self, entry):
        content = entry.content
        if content:
            content = zlib.compress(entry.content.encode())
            content = binascii.b2a_base64(content).decode().rstrip()
        signature = binascii.b2a_base64(entry.signature).decode().rstrip()
        return ' '.join(map(str, (entry.hash, entry.parent_hash, entry.time, entry.fingerprint,
                                  entry.action, entry.path, content, signature)))
    
    def decode(self, line):
        hash, parent_hash, time, fingerprint, action, path, content, signature = line.split(' ')
        if content:
            content = binascii.a2b_base64(content.encode())
            content = zlib.decompress(content).decode()
        signature = binascii.a2b_base64(signature.encode())
        time = int(time)
        return LogEntry(self, parent_hash, action, path, content,
            time=time, fingerprint=fingerprint, signature=signature)
    
    def load(self, clear=False):
        """ loads logfile """
        if clear:
            self.entries_by_parent.clear()
            self.entries.clear()
            self.keys.clear()
            self.loaded = 0
        with open(self.logpath, 'r') as log:
            # Read all log entries
            log.seek(self.loaded)
            for line in log.readlines():
                entry = self.decode(line)
                # 0: root, 1: .keys, 2: .cluster
                if not self.root:
                    self.root = entry
                elif not self.root_keys:
                    self.root_keys = entry
                elif not self.root_cluster:
                    self.root_cluster = entry
                entry.validate()
                entry.clean()
                self.add_entry(entry)
            self.loaded = log.tell()
        return self.root
    
    def add_entry(self, entry):
        if entry.path.endswith(os.sep + '.keys'):
            self.keys.update(entry.read_keys())
        self.entries[entry.hash] = entry
        self.entries_by_parent[entry.parent_hash].append(entry)
    
    def bootstrap(self, keys, ips):
        root_key = keys[0]
        self.root = self.mkdir(parent=None, path='/', key=root_key)
        keys = '\n'.join((key.oneliner() for key in keys)) + '\n'
        self.root_keys = self.write(parent=self.root, path='/.keys', content=keys, key=root_key)
        ips = '\n'.join(ips) + '\n'
        self.root_cluster = self.write(parent=self.root, path='/.cluster', content=ips, key=root_key)
        with open(self.logpath, 'r') as log:
            self.loaded = log.seek(0, 2)
    
    def do_action(self, parent, action, path, key, *content, commit=True):
        path = os.path.normpath(path)
        entry = LogEntry(self, parent, action, path, *content)
        if parent and parent.action == entry.action:
            entry.ctime = parent.ctime
        else:
            entry.ctime = entry.time
        entry.clean()
        if commit:
            entry.sign(key)
            self.save(entry, key)
        else:
            entry.hash = id(entry)
            entry.fingerprint = key.fingerprint
        self.add_entry(entry)
        return entry
    
    def validate(self, entry):
        if self.keys:
            # Rootkey is already loaded
            key = self.keys[entry.fingerprint]
            entry.verify(key)
    
    def mkdir(self, parent, path, key, commit=True):
        return self.do_action(parent, LogEntry.MKDIR, path, key, commit=commit)
    
    def write(self, parent, path, content, key, commit=True):
        return self.do_action(parent, LogEntry.WRITE, path, key, content, commit=commit)
    
    def delete(self, parent, path, key, commit=True):
        return self.do_action(parent, LogEntry.DELETE, path, key, commit=commit)
    
    def save(self, entry, key=None):
        with open(self.logpath, 'a') as logfile:
            logfile.write(self.encode(entry) + '\n')


class LogEntry(object):
    MKDIR = 'MKDIR'
    WRITE = 'WRITE'
    DELETE = 'DELETE'
    ACTIONS = set((MKDIR, WRITE, DELETE))
    ROOT_PARENT_HASH = '0'*32
    
    def __str__(self):
        content = self.content.replace('\n', '\\n')
        tail = '...' if len(content) > 32 else ''
        return '{%s %s %s %s%s %s}' % (
            self.action, self.path, self.hash, content[:32], tail, self.fingerprint)
    
    def __repr__(self):
        return str(self)
    
    def __init__(self, log, parent, action, path, *content, **kwargs):
        self.time = kwargs.get('time') or int(time.time())
        if isinstance(parent, LogEntry):
            self.parent_hash = parent.hash
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
    def parent(self):
        if self.parent_hash != self.ROOT_PARENT_HASH:
            return self.log.entries[self.parent_hash]
    
    @property
    def childs(self):
        if hasattr(self, '_childs'):
            return self._childs
        return self.log.entries_by_parent[self.hash]
    
    def clean(self):
        """ cleans log entry """
        self.path = os.path.normpath(self.path.strip())
        if self.action not in self.ACTIONS:
            raise ValidationError("'%s' not a valid action type" % self.action)
        if self.parent:
            dirname = os.path.dirname(self.path)
            if self.parent.action == self.MKDIR:
                if ((self.action == self.WRITE and self.parent.path != dirname) or
                    (self.action == self.MKDIR and self.parent.path != dirname and self.parent.path != self.path)):
                        raise ValidationError("%s to path '%s' when is not the parent of '%s' ('%s')"
                            % (self.action, self.parent.path, self.path, dirname))
            elif self.parent.action == self.WRITE:
                if self.action == self.MKDIR:
                    raise ValidationError("'MKDIR %s' after 'WRITE %s'"
                        % (self.path, self.parent.path))
                elif self.parent.path != self.path:
                    raise ValidationError("%s to parent path '%s' when is not the same as '%s'"
                        % (self.action, self.parent.path, self.path))
            if self.action == self.DELETE and self.parent.path != self.path:
                raise ValidationError("%s to parent path '%s' when is not the same as '%s'"
                    % (self.action, self.parent.path, self.path))
        if os.path.basename(self.path) == '.keys':
            if self.action is self.MKDIR:
                raise ValidationError(".keys can not be a directory.")
            elif self.action is self.WRITE:
                # Validates keys
                self.read_keys()
        if not re.match(r'^[0-9a-f]{32}$', self.parent_hash):
            raise ValidationError("%s not a valid md5 hash" % self.parent_hash)
        if self.hash in self.log.entries:
            raise IntegrityError("%s already exists" % self.hash)
    
    def get_key(self, keys, last_keys):
        for fingerprint, key in itertools.chain(keys.items(), last_keys.items()):
            if self.fingerprint == fingerprint:
                return key
    
    def rec_get_branch_state(self, score, path, keys, last, pending):
        """ gets last blockchain entry """
        last_keys = {}
        # Needed for processing .key chain
        if last and os.path.basename(last.path) == '.keys':
            last_keys = last.read_keys()
        key = self.get_key(keys, last_keys)
        if key:
            _score = Score(key)
            if score:
                score += _score
            else:
                score = _score
            # account for revoked shit
            for fingerprint in pending:
                score += Score(fingerprint)
            last = self
            del pending[:]
        else:
            # Maybe the key has been revoked, just store on pending for scoring if needed
            pending.append(self.fingerprint)
        selected = None
        for child in self.childs:
            # needed for processing mkdir branches
            if child.path == path:
                child_score, child_last = child.rec_get_branch_state(
                    score, path, keys, last, pending)
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
                entry._childs = entries
                entry.is_mocked = True
        else:
            entry = self
        score, last = entry.rec_get_branch_state(Score(), entry.path, keys, None, [])
        if getattr(last, 'is_mocked', False):
            return Score(), None
        if last:
            last.ctime = entry.time
        return score, last
    
    def read_keys(self):
        keys = {}
        for line in self.content.splitlines():
            line = line.strip()
            line = '-----BEGIN EC PRIVATE KEY-----\n' + line + '-----END EC PRIVATE KEY-----'
            key = Key.from_pem(line)
            keys[key.fingerprint] = key
        return keys
    
    def get_hash(self):
        line = ' '.join(map(str, (self.parent_hash, self.time, self.action, self.path,
                                  self.content, self.fingerprint)))
        return hashlib.md5(line.encode()).hexdigest()
    
    def sign(self, key=None):
        key = key or self.log.keys[self.fingerprint]
        pre_self = self.log.entries.pop(self.hash, None)
        pre_childs = self.log.entries_by_parent.pop(self.hash, None)
        self.fingerprint = key.fingerprint
        self.hash = self.get_hash()
        self.signature = key.sign(self.hash.encode())
        if pre_childs is not None:
            for child in pre_childs:
                child.parent_hash = self.hash
            self.log.entries_by_parent[self.hash] = pre_childs
        if pre_self is not None:
            self.log.entries[self.hash] = self
    
    def verify(self, key):
        if not self.hash:
            self.hash = self.get_hash()
        vk = key.get_verifying_key()
        if not vk.verify(self.signature, self.hash.encode()):
            raise ValidationError("Failed hash verification %s %s" % (self.hash, self.fingerprint))
    
    def save(self):
        self.log.save(self)
    
    def validate(self):
        self.log.validate(self)


# TODO count upper-class keys first (needed for key revokation)
class Score(object):
    """ allways growing datastructure
    proof-of-stake: higher keys win """
    
    def __str__(self):
        return "min: %s keys: %s" % (self.min_path, len(self.keys))
    
    def __init__(self, *keys):
        self.min_path = sys.maxsize
        self.keys = set()
        for key in keys:
            if isinstance(key, Key):
                count = 0 if key.upper_path == '/' else key.upper_path.count(os.sep)
                self.min_path = min(self.min_path, count)
                self.keys.add(key.fingerprint)
            else:
                self.keys.add(key)
    
    def __add__(self, score):
        self.min_path = min(self.min_path, score.min_path)
        self.keys = self.keys.union(score.keys)
        return self
    
    def __gt__(self, score):
        return self.min_path < score.min_path or (self.min_path == score.min_path and len(self.keys) > len(score.keys))
    
    def __lt__(self, score):
        return self.min_path > score.min_path or (self.min_path == score.min_path and len(self.keys) < len(score.keys))
    
    def __eq__(self, score):
        return self.min_path == score.min_path and len(self.keys) == len(score.keys)
