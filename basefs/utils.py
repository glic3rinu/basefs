import collections
import os
import socket
import subprocess


class Candidate:
    def __init__(self, score, entry):
        self.score = score
        self.entry = entry
    
    def __gt__(self, candidate):
        """ self better than candidate """
        return (
            self.score > candidate.score or (
                self.score == candidate.score and self.entry.hash > candidate.entry.hash)
        )


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self
    
    def __hash__(self):
        return hash(id(self))


def issubdir(path, directory):
    path = os.path.realpath(path)
    directory = os.path.realpath(directory)
    relative = os.path.relpath(path, directory)
    return not relative.startswith(os.pardir)


def touch(fname, times=None):
    with open(fname, 'a'):
        os.utime(fname, times)


import asyncio

def netcat(host, port, content):
#    @asyncio.coroutine
#    def coro():
#        reader, writer = yield from asyncio.open_connection(host, port)
#        writer.write(content.encode()+b'\n')
#        data = yield from reader.read(1024)
#        writer.close()
#        print(data)
#        return data
#    loop = asyncio.get_event_loop()
#    task = asyncio.async(coro())
#    return loop.run_until_complete(task)
        
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, int(port)))
    s.sendall(content)
    s.shutdown(socket.SHUT_WR)
    while True:
        recv = s.recv(2048)
        if not recv:
            s.close()
            raise StopIteration
        yield recv.decode()


def get_mount_info(*args):
    if not args:
        path = os.getcwd()
    else:
        path = args[0]
    while path != os.sep:
        if os.path.ismount(path):
            mount = subprocess.Popen('mount', stdout=subprocess.PIPE)
            mount.wait()
            for line in mount.stdout.readlines():
                info, __, mountpoint = line.split()[:3]
                info = info.decode()
                logpath = ':'.join(info.split(':')[:-1])
                if path == mountpoint.decode() and os.path.isfile(logpath):
                    # Validate logfile
                    with open(logpath, 'r') as log:
                        line = log.readline()
                    line = line.split(' ')
                    if len(line) == 8 and line[1].startswith('0'*16) and line[4] == 'MKDIR' and line[5] == os.sep:
                        return AttrDict(
                            logpath=logpath,
                            port=int(info.split(':')[-1]),
                            mountpoint=mountpoint.decode(),
                        )
            
            return
        path = os.path.abspath(os.path.join(path, os.pardir))


class LRUCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.cache = collections.OrderedDict()
    
    def __str__(self):
        return str(self.cache)
    
    def get(self, key):
        try:
            value = self.cache.pop(key)
            self.cache[key] = value
            return value
        except KeyError:
            return -1
    
    def set(self, key, value):
        try:
            self.cache.pop(key)
        except KeyError:
            if len(self.cache) >= self.capacity:
                self.cache.popitem(last=False)
        self.cache[key] = value
    
    def pop(self, key, *default):
        return self.cache.pop(key, *default)
    
    def items(self):
        return self.cache.items()


class Signal(object):
    def __init__(self):
        self._registry = []
    
    def connect(self, func):
        self._registry.append(func)
    
    def send(self, *args, **kwargs):
        for func in self._registry:
            func(*args, **kwargs)


class OrderedSet(collections.MutableSet):
    def __init__(self, iterable=None):
        self.end = end = [] 
        end += [None, end, end]         # sentinel node for doubly linked list
        self.map = {}                   # key --> [key, prev, next]
        if iterable is not None:
            self |= iterable
    
    def __len__(self):
        return len(self.map)
    
    def __contains__(self, key):
        return key in self.map
    
    def add(self, key):
        if key not in self.map:
            end = self.end
            curr = end[1]
            curr[2] = end[1] = self.map[key] = [key, curr, end]
    
    def discard(self, key):
        if key in self.map:        
            key, prev, next = self.map.pop(key)
            prev[2] = next
            next[1] = prev
    
    def __iter__(self):
        end = self.end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]
    
    def __reversed__(self):
        end = self.end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]
    
    def pop(self, last=True):
        if not self:
            raise KeyError('set is empty')
        key = self.end[1][0] if last else self.end[2][0]
        self.discard(key)
        return key
    
    def union(self, *sets):
        new = type(self)(self)
        for s in sets:
            for e in s:
                new.add(e)
        return new
    
    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))
    
    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)
