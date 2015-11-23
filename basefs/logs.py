import base64
import binascii
import copy
import hashlib
import ipaddress
import itertools
#import lzma vs zlib
import os
import re
import sys
import time
import zlib
from collections import defaultdict

from . import utils, signals
from .keys import Key
from .exceptions import ValidationError, Exists
from .utils import Candidate


class Log:
    root = None
    root_key = None
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
        self.blocks = {}
        self.blocks_by_parent = {}
        self.keys_by_name = {}
        self.post_create = utils.Signal()
    
    def print_tree(self, entry=None, indent='', view=None, color=False, ascii=False, values=None):
        if entry is None:
            entry = self.root
        ret = repr(entry) + '\n'
        if view:
            if not values:
                values = set()
                for node in view.paths.values():
                    values.add(node.entry.hash)
                    if node.perm:
                        values.add(node.perm.entry.hash)
            bootstrap = entry.hash in (self.root.hash, self.root_cluster.hash, self.root_key.hash)
            if color and bootstrap:
                ret = '\033[1m\033[94m' + ret + '\033[0m'
            if entry.hash in values:
                ret = '*' + ret
                if color and not bootstrap:
                    ret = '\033[1m\033[92m' + ret + '\033[0m'
        childs = self.entries_by_parent[entry.hash]
        if not childs:
            return ret
        for child in childs[:-1]:
            sep = '  |-' if ascii else '  ├─'
            ret += indent + sep
            sep = '  | ' if ascii else '  │ '
            ret += self.print_tree(child, indent+sep, view, color, ascii, values=values)
        child = childs[-1]
        sep = '  `-' if ascii else '  └─'
        ret += indent + sep
        ret += self.print_tree(child, indent + '    ', view, color, ascii, values=values)
        return ret
    
    def encode(self, entry):
        if isinstance(entry, Block):
            content = binascii.b2a_base64(entry.content).decode().rstrip()
            return ' '.join(('B', entry.hash, str(entry.next_hash), content))
#       content = entry.content
#       if content:
#           content = zlib.compress(entry.content.encode())
#           content = binascii.b2a_base64(content).decode().rstrip()
        signature = binascii.b2a_base64(entry.signature).decode().rstrip()
        return ' '.join((entry.hash, entry.parent_hash, str(entry.timestamp), entry.fingerprint,
                         entry.action, entry.name, str(entry.content), signature))
    
    def decode(self, line, log=None):
        if line.startswith('B'):
            __, hash, next_hash, content = line.split()
            if next_hash == 'None':
                next_hash = None
            offset = None
            if log:
                offset = log.tell()
                offset = (offset-len(content), offset)
            content = binascii.a2b_base64(content)
            return Block(self, next_hash, content, hash=hash, offset=offset)
        line = line.split(' ')
        hash, parent_hash, timestamp, fingerprint, action = line[:5]
        path = ' '.join(line[5:-2])
        content, signature = line[-2:]
#        if content:
#            content = binascii.a2b_base64(content.encode())
#            content = zlib.decompress(content).decode()
        signature = binascii.a2b_base64(signature.encode())
        timestamp = int(timestamp)
        return LogEntry(self, parent_hash, action, path, content,
            timestamp=timestamp, fingerprint=fingerprint, signature=signature)
    
    def load(self, clear=False):
        """ loads logfile """
        if clear:
            self.entries_by_parent.clear()
            self.entries.clear()
            self.blocks.clear()
            self.blocks_by_parent.clear()
            self.keys.clear()
            self.keys_by_name.clear()
            self.loaded = 0
        with open(self.logpath, 'r') as log:
            # Read all log entries
            log.seek(self.loaded)
            for line in log.readlines():
                entry = self.decode(line, log)
                if isinstance(entry, Block):
                    block = entry
                    self.add_block(block)
                else:
                    # 0: root, 1: .keys, 2: .cluster
                    if not self.root:
                        self.root = entry
                    elif not self.root_key:
                        self.root_key = entry
                    elif not self.root_cluster:
                        self.root_cluster = entry
                    # TODO option to run cleaning somehow
#                    entry.validate()
#                    entry.clean()
                    self.add_entry(entry)
            self.loaded = log.tell()
        if not self.root:
            raise RuntimeError("Empty logfile %s" % self.logpath)
        for entry in self.entries.values():
            if entry.action == entry.WRITE:
                entry.next_block = None
                try:
                    next = self.blocks[entry.content]
                except KeyError:
                    entry.next_block = entry.content
                else:
                    while next:
                        try:
                            next = next.next
                        except KeyError:
                            entry.next_block = next.next_hash
                            break
        return self.root
    
    def add_entry(self, entry):
        if entry.action == entry.GRANT:
            key = entry.read_key()
            self.keys[key.fingerprint] = key
            try:
                self.keys_by_name[entry.name].add(key)
            except KeyError:
                self.keys_by_name[entry.name] = set([key])
        self.entries[entry.hash] = entry
        self.entries_by_parent[entry.parent_hash].append(entry)
    
    def add_block(self, block):
        self.blocks[block.hash] = block
        if block.next_hash:
            self.blocks_by_parent[block.next_hash] = block
    
    def bootstrap(self, keys, ips):
        root_key = keys[0]
        self.root = self.mkdir(parent=None, name='/', key=root_key)
        parent = self.root
        for ix, key in enumerate(keys):
            name = 'root'
            if ix:
                name = 'root-%s' % ix
            parent = self.grant(parent=parent, name=name, key=root_key, content=key)
            if not ix:
                self.root_key = parent
        # Validate ips: ['ip:port']
        content = ''
        for ip in ips:
            ip, port = ip.split(':')
            ip = ipaddress.ip_address(ip)
            port = int(port)
            content += '%s:%s\n' % (ip, port)
        from .views import View
        view = View(self, root_key)
        view.build()
        view.write('/.cluster', content)
    
    def do_action(self, parent, action, name, key, *args, commit=True):
        entry = LogEntry(self, parent, action, name, *args)
        entry.next_block = None
        if parent and parent.action == entry.action:
            entry.ctime = parent.ctime
        else:
            entry.ctime = entry.timestamp
        entry.clean()
        if commit:
            entry.sign(key)
            entry.save()
        else:
            entry.hash = id(entry)
            entry.fingerprint = key.fingerprint
        self.add_entry(entry)
        self.post_create.send(entry)
        return entry
    
    def validate(self, entry):
        if self.keys:
            # Rootkey is already loaded
            key = self.keys[entry.fingerprint]
            entry.verify(key)
    
    def mkdir(self, parent, name, key, commit=True):
        return self.do_action(parent, LogEntry.MKDIR, name, key, commit=commit)
    
    def write(self, parent, name, key, attachment=None, content=None, commit=True):
        blocks = []
        if attachment:
            next_hash = None
            first = 355 - len(name)  # 512 - (1+28+4+1+1+0+1+28+16+48 +1+28) - len(name)
            # 483 = 512 - 28 -1
            for ix in reversed(range(first, len(attachment), 483)):
                block = Block(self, next_hash, attachment[ix:ix+483])
                next_hash = block.hash
                blocks.insert(0, block)
            block = Block(self, next_hash, attachment[:first])
            blocks.insert(0, block)
        if not content:
            content = block.hash
        response = self.do_action(parent, LogEntry.WRITE, name, key, content, commit=commit)
        for block in blocks:
            self.add_block(block)
            if commit:
                block.save()
        return response
    
    def delete(self, parent, name, key, commit=True):
        return self.do_action(parent, LogEntry.DELETE, name, key, commit=commit)
    
    def get_key(self, name):
        try:
            # by fingerprint
            return self.keys[name]
        except KeyError:
            grant_keys = self.keys_by_name[name]
            if len(grant_keys) > 1:
                fingers = [k.fingerprint for k in grant_keys]
                raise ValueError("Multiple values for key name %s: %s." % (name, fingers))
            return next(iter(grant_keys))
    
    def grant(self, parent, name, key, content=None, commit=True):
        # Validate key consistency
        try:
            grant_key = self.get_key(name)
        except KeyError:
            if content:
                fingerprint = content.fingerprint
                if fingerprint in self.keys:
                    raise KeyError("fingerprint %s for key %s already exists." % (fingerprint, name))
                grant_key = content
        if content and content != grant_key:
            cfinger = content.fingerprint
            gfinger = grant_key.fingerprint
            raise KeyError("Provided key doesn't match with key %s: %s != %s" % (name, cfinger, gfinger))
        content = grant_key.oneliner()
        return self.do_action(parent, LogEntry.GRANT, name, key, content, commit=commit)
    
    def revoke(self, parent, name, key, commit=True):
        rev_key = self.get_key(name)
        fingerprint = rev_key.fingerprint
        return self.do_action(parent, LogEntry.REVOKE, name, key, fingerprint, commit=commit)
    
    def save(self, entry):
        signals.send(type(entry).save, entry)
        with open(self.logpath, 'a') as logfile:
            logfile.write(self.encode(entry) + '\n')
            self.loaded = logfile.tell()
    
    def find(self, path):
        return self.root.find(path)


class LogEntry:
    MKDIR = 'MKDIR'
    WRITE = 'WRITE'
    DELETE = 'DELETE'
    REVOKE = 'REVOKE'
    GRANT = 'GRANT'
    SLINK = 'SLINK'
    LINK = 'LINK'
    REVERT = 'REVERTE'
    MODE = 'MODE'
    ACK = 'ACK'
    ACTIONS = set((MKDIR, WRITE, DELETE, GRANT, REVOKE, LINK, SLINK, REVERT, MODE, ACK))
    HASH_SIZE = 56
    ROOT_PARENT_HASH = '0'*HASH_SIZE
    
    def __str__(self):
        content = self.content.replace('\n', '\\n')
        tail = '...' if len(content) > 32 else ''
        return '{%s %s %s %s%s %s}' % (
            self.action, self.name, self.hash, content[:32], tail, self.fingerprint)
    
    def __repr__(self):
        return str(self)
    
    def __init__(self, log, parent, action, name, *content, **kwargs):
        self.timestamp = kwargs.pop('timestamp', None) or int(time.time())
        if isinstance(parent, LogEntry):
            self.parent_hash = parent.hash
        else:
            self.parent_hash = parent or self.ROOT_PARENT_HASH
        self.action = action
        self.name = name
        self.log = log
        self.hash = kwargs.pop('hash', None)
        self.fingerprint = kwargs.pop('fingerprint', None)
        self.signature = kwargs.pop('signature', None)
        if kwargs:
            raise ValueError("Unkown %s kwargs" % kwargs)
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
    
    @property
    def path(self):
        # TODO lINK and GOTO and ACK
        if not hasattr(self, '_path'):
            if not self.parent:
                self._path = os.sep
            else:
                if self.action in (self.REVOKE, self.GRANT):
                    self._path = self.parent.path
                elif self.parent.action == self.DELETE or self.action == self.DELETE:
                    self._path = self.parent.path
                elif self.parent.action == self.action == self.WRITE:
                    self._path = self.parent.path
                else:
                    self._path = os.path.join(self.parent.path, self.name)
        return self._path
    
    def get_blocks(self):
        next = self.log.blocks[self.content]
        while next:
            yield next
            next = next.next
    
    def get_content(self):
        if not hasattr(self, '_content'):
            if not self.content:
                self._content = self.content
            else:
                content = b''
                for block in self.get_blocks():
                    content += block.content
                self._content = content
        return self._content
    
    def clean(self):
        """ cleans log entry """
        self.name = os.path.normpath(self.name.strip())
        if self.action not in self.ACTIONS:
            raise ValidationError("Entry with '%s' not a valid action type" % self.action)
        if self.parent:
            if self.parent.action == self.WRITE:
                if self.action == self.MKDIR:
                    raise ValidationError("'MKDIR %s' after 'WRITE %s'"
                        % (self.path, self.parent.path))
                if self.action in (self.GRANT, self.REVOKE):
                    try:
                        self.read_key()
                    except:
                        raise ValidationError("Invalid EC public key '%s'." % self.content)
        if not re.match(r'^[0-9a-f]{%i}$' % self.HASH_SIZE, self.parent_hash):
            raise ValidationError("Entry %s not a valid sha224 hash" % self.parent_hash)
        if self.hash in self.log.entries:
            raise Exists("Entry %s already exists" % self.hash)
    
    def get_key(self, keys, last_keys):
        for fingerprint, key in itertools.chain(keys.items(), last_keys.items()):
            if self.fingerprint == fingerprint:
                return key
    
    # TODO blockchain terminology
    def rec_get_branch_state(self, score, name, keys, last, pending, branch_keys, path=None):
        """ gets last blockchain entry """
        key = self.get_key(keys, branch_keys)
        if key:
            # Needed for processing .key chain
            if self.action == self.GRANT:
                key = self.read_key()
                key.upper_path = path
                branch_keys[key.fingerprint] = key
            elif self.action == self.REVOKE:
                finger = self.content
                branch_keys.pop(finger, None)
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
            perms = self.action in (self.REVOKE, self.GRANT) and child.action in (self.REVOKE, self.GRANT)
            if perms or not perms and child.name == name:
                child_score, child_last = child.rec_get_branch_state(
                    score, name, keys, last, pending, branch_keys, path)
                if child_last is not None:
                    candidate = Candidate(score=child_score, entry=child)
                    if not selected or candidate > selected:
                        selected = candidate
                        selected.last = child_last
        if selected:
            return score, selected.last
        return score, last
    
    def find(self, path):
        if self.path == path:
            return self
        else:
            for child in self.childs:
                if child.action not in (self.GRANT, self.REVOKE):
                    if utils.issubdir(child.path, path):
                        entry = child.find(path)
                        if entry:
                            return entry
    
    def get_branch_state(self, keys, *entries, path=None):
        if entries:
            if len(entries) == 1:
                entry = entries[0]
            else:
                # Conflicting initial branches, create a fake node to allow the rec call
                entry = copy.copy(entries[0])
                entry._childs = entries
                entry.is_mocked = True
        else:
            entry = self
        branch_keys = {}
        score, last = entry.rec_get_branch_state(Score(), entry.name, keys, None, [], branch_keys, path)
        if getattr(last, 'is_mocked', False):
            raise RuntimeError("At least one branch should have been selected")
        if last:
            last.branch_keys = branch_keys
            last.ctime = entry.timestamp
        return score, last
    
    def read_key(self):
        content = (
            '-----BEGIN EC PRIVATE KEY-----\n' +
            self.content +
            '-----END EC PRIVATE KEY-----'
        )
        key = Key.from_pem(content)
        try:
            return self.log.keys[key.fingerprint]
        except KeyError:
            self.log.keys[key.fingerprint] = key
        return key
    
    def get_hash(self):
        line = ' '.join(map(str, (self.parent_hash, self.timestamp, self.action, self.name,
                                  self.content, self.fingerprint)))
        return hashlib.sha224(line.encode()).hexdigest()
    
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


class Block:
    HASH_SIZE = 56
    
    def __str__(self):
        return "[%s %s %s]" % (self.hash, self.next_hash, self.content[:32])
    
    def __repr__(self):
        return str(self)
    
    def __init__(self, log, next_hash, *content, hash=None, offset=None):
        self.log = log
        self.next_hash = next_hash
        if offset:
            self.ini, self.end = offset
        if content:
            self._content = content[0]
        self.hash = hash
        if not self.hash:
            self.hash = self.get_hash()
    
    def get_hash(self):
        content = (self.next_hash or str(None)).encode() + self.content
        return hashlib.sha224(content).hexdigest()
    
    def clean(self):
        if self.next_hash is not None:
            if not re.match(r'^[0-9a-f]{%i}$' % self.HASH_SIZE, self.next_hash):
                raise ValidationError("Block %s not a valid sha224 hash" % self.next_hash)
        if self.hash in self.log.blocks:
            raise Exists("Block %s already exists" % self.hash)
    
    @property
    def next(self):
        if self.next_hash:
            return self.log.blocks[self.next_hash]
        return None
    
    @property
    def previous(self):
        return self.log.blocks_by_parent[self.hash]
    
    @property
    def content(self):
        if not hasattr(self, '_content'):
            with open(self.log.logpath) as log:
                log.seek(self.ini)
                content = self.log.read(self.end)
            self._content = content
        return self._content
    
    def save(self):
        self.log.save(self)


# TODO count upper-class keys first (needed for key revokation)
class Score:
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
