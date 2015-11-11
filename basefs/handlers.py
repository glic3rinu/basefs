# TODO: maybe fs does not save anything an everything is handled by this motherfucker?
# or maybe FS just calls on this guy like sftp does ?

import asyncio
import functools
import itertools
import os
import random
import socket
from collections import defaultdict

from . import exceptions
from .logs import Log
from .messages import SerfClient
from .views import View


def get_entries(entry, eq_path=False):
    # TODO
    yield entry
    for child in entry.childs:
        if not eq_path or entry.action in (entry.GRANT, entry.REVOKE) or child.name == entry.name:
            print(child)
            yield from get_entries(child)


class BasefsSyncProtocol(asyncio.Protocol):
    LS = 'LS'
    ENTRY_REQ = 'E-REQ'
    PATH_REQ = 'P-REQ'
    ENTRIES = 'ENTRIES'
    CLOSE = 'CLOSE'
    merkle = {}
    tree = defaultdict(list)
    
    def __init__(self, view, serf, client=False, hostname=None):
        super(BasefsSyncProtocol, self).__init__()
        self.view = view
        self.log = view.log
        self.serf = serf
        self.client = client
        self.hostname = hostname or socket.gethostname()
    
    def encode(self, data):
        # TODO compress or whatever
        return b's' + data.encode()
    
    def decode(self, data):
        return data.decode()[1:]
    
    def encode_entry(self, entry):
        # TODO remove unthrosworthy shit (hash) and whatever
        return self.log.encode(entry)
    
    def decode_entry(self, line):
        return self.log.decode(line)
    
    def connection_made(self, transport):
        """
        Called when a connection is made.
        The argument is the transport representing the pipe connection.
        To receive data, wait for data_received() calls.
        When the connection is closed, connection_lost() is called.
        """
        self.transport = transport
        if self.client:
            request = self.initial_request()
            self.transport.write(request)
    
    def sync_received(self, data):
        print('sync-received', data)
        lines = self.decode(data).splitlines()
        entries_to_send = set()
        entries_to_request = set()
        paths_to_send = set()
        paths_to_request = set()
        verified_paths = set()
        ls = set()
        ls_path = None
        close = False
        for line in lines:
            if line in (self.LS, self.ENTRY_REQ, self.PATH_REQ, self.ENTRIES, self.CLOSE):
                mode = line
                continue
            if mode == self.LS:
                line = line.split()
                if line[0].startswith('*'):
                    # path entries
                    ls_path, rentries = line[0], set(line[1:])
                    ls_path = ls_path[1:]
                    lentries = set([lentry.hash for lentry in get_entries(self.log.find(ls_path), eq_path=True)])
                    entries_to_send = entries_to_send.union(lentries - rentries)
                    entries_to_request = entries_to_request.union(rentries - lentries)
                else:
                    path, rhash = line
                    try:
                        lhash = self.merkle[path]
                    except KeyError:
                        paths_to_request.add(path)
                    else:
                        if hex(lhash)[2:] != rhash:
                            ls.add(path)
                        else:
                            verified_paths.add(path)
            elif mode == self.ENTRY_REQ:
                entries_to_send.add(line)
            elif mode == self.PATH_REQ:
                paths_to_send.add(line)
            elif mode == self.ENTRIES:
                entry = self.decode_entry(line)
                try:
                    entry.clean()
                    entry.validate()
                except exceptions.ValidationError:
                    pass
                else:
                    self.log.add_entry(entry)
                    entry.save()
                    self.update_merkle(entry)
        if mode == self.CLOSE:
            self.transport.close()
            # TODO
            return
        if ls_path:
            paths_to_send = paths_to_send.union(set(self.tree[ls_path]) - (paths_to_request.union(ls, verified_paths)))
        response = []
        if ls:
            response.append(self.LS)
            for path in ls:
                ls_entries = get_entries(self.log.find(path), eq_path=True)
                ls_entries = [entry.hash for entry in ls_entries]
                response.append('*%s ' % path + ' '.join(ls_entries))
                for cpath in self.tree[path]:
                    response.append('%s %s' % (cpath, hex(self.merkle[cpath])[2:]))
        if entries_to_request:
            response.append(self.ENTRY_REQ)
            response.extend(entries_to_request)
        if paths_to_request:
            response.append(self.PATH_REQ)
            response.extend(paths_to_request)
        if not response:
            close = True
        if entries_to_send or paths_to_send:
            response.append(self.ENTRIES)
            for ehash in entries_to_send:
                response.append(self.encode_entry(self.log.entries[ehash]))
            for path in paths_to_send:
                print(self.log.find(path), path, self.log.print_tree())
                print(list(get_entries(self.log.find(path))))
                for entry in get_entries(self.log.find(path)):
                    print(entry)
                    if entry.hash not in entries_to_send:
                        response.append(self.log.encode(entry))
        if close:
            response.append(self.CLOSE)
        response = '\n'.join(response)
        print('response', self.encode(response))
        self.transport.write(self.encode(response))
        if close:
            self.transport.close()
    
    def entry_received(self, data):
        entry = self.serf.receive(data[1:].strip())
        entry.clean()
        entry.validate()
        print('received entry', entry)
        self.log.save(entry)
        self.log.add_entry(entry)
        self.update_merkle(entry)
        self.view.build()
    
    def data_received(self, data):
        """
        Called when some data is received.
        The argument is a bytes object.
        """
        if data[0] == 115:
            self.sync_received(data)
        elif data[0] == 101:
            self.entry_received(data)
        else:
            print('UNKNOWN TOKEN', data[0])
    
    # TODO view.load() if updated
#    def connection_lost(self, exc):
#        """
#        Called when the connection is lost or closed.
#        The argument is an exception object or None (the latter
#        meaning a regular EOF is received or the connection was
#        aborted or closed).
#        """
#        print("Connection lost! Closing server...")
#        self.server.close()
    
    @classmethod
    def update_merkle(cls, entry):
        hash = int(entry.hash, 16)
        path = os.sep
        for part in itertools.chain(entry.path.split(os.sep)):
            path = os.path.join(path, part)
            try:
                cls.merkle[path] ^= hash
            except KeyError:
                cls.merkle[path] = hash
                if os.path.dirname(path) != path:
                    cls.tree[os.path.dirname(path)].append(path)
    
    def initial_request(self):
        request = [
            'LS',
            '%s %s' % (os.sep, hex(self.merkle[os.sep])[2:])
        ]
        return self.encode('\n'.join(request))


@asyncio.coroutine
def do_full_sync(client_factory, serf, hostname):
    paths = None
    loop = asyncio.get_event_loop()
    def get_member():
        members = serf.members()
        members = members.body[b'Members']
        random.shuffle(members)
        for member in members:
            if member[b'Status'] == b'alive' and member[b'Name'] != hostname.encode():
                return member[b'Addr'].decode(), member[b'Port']+2
        return None, None
    while True:
        print('do full sync')
        yield from asyncio.sleep(10) #1000000) # random.randint(5, 10))  # switch to other code and continue execution in 5 seconds
        ip, port = get_member()
        if ip:
            coro = loop.create_connection(client_factory, ip, port)
            asyncio.async(coro)


def run(view, serf, port, hostname=None):
    protocol = BasefsSyncProtocol(view, serf, hostname=hostname)
    for entry in view.log.entries.values():
        BasefsSyncProtocol.update_merkle(entry)
    server_factory = lambda: BasefsSyncProtocol(view, serf, hostname=hostname)
    client_factory = lambda: BasefsSyncProtocol(view, serf, hostname=hostname, client=True)
    print('server on', port)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    server = loop.run_until_complete(loop.create_server(server_factory, '0.0.0.0', port))
    asyncio.async(do_full_sync(client_factory, serf, hostname))
    try:
        loop.run_until_complete(server.wait_closed())
    finally:
        loop.close()
