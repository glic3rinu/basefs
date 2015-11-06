# TODO: maybe fs does not save anything an everything is handled by this motherfucker?
# or maybe FS just calls on this guy like sftp does ?

import asyncio
import functools
import itertools
import os
from collections import defaultdict

from .logs import Log
from .messages import SerfClient
from .views import View


def get_entries(entry):
    yield entry
    for child in entry.childs:
        yield get_entries(entry)


class FullSyncProtocol(asyncio.Protocol):
    def __init__(self, log, *args, cport=0, **kwargs):
        super(FullSyncProtocol, self).__init__(*args, **kwargs)
        self.log = log
        self.tree = defaultdict(list)
        self.merkle = {}
        self.cport = cport
        for entry in self.log.entries.values():
            self.update_merkle(entry)
    
    def connection_made(self, transport):
        """
        Called when a connection is made.
        The argument is the transport representing the pipe connection.
        To receive data, wait for data_received() calls.
        When the connection is closed, connection_lost() is called.
        """
        self.transport = transport
 
    def data_received(self, data):
        """
        Called when some data is received.
        The argument is a bytes object.
        """
        lines = data.decode().splitlines()
        entries_to_send = set()
        entries_to_request = set()
        paths_to_send = set()
        paths_to_request = set()
        verified_paths = set()
        ls = set()
        ls_path = None
        close = False
        for line in lines:
            if line in ('LS', 'E-REQ', 'P-REQ', 'ENTRIES', 'CLOSE'):
                mode = line
                continue
            if mode == 'LS':
                line = line.split()
                if line[0].startswith('*'):
                    # path entries
                    ls_path, rentries = line[0], set(line[1:])
                    lentries = set([lentry.hash for lentry in get_entries(self.log.find(ls_path))])
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
            elif mode == 'E-REQ':
                entries_to_send.add(line)
            elif mode == 'P-REQ':
                paths_to_send.add(line)
            elif mode == 'ENTRIES':
                entry = self.log.decode(line)
                entry.validate()
                entry.save()
        if mode == 'CLOSE':
            self.transport.close()
            # TODO
            return
        if ls_path:
            paths_to_send = paths_to_send.union(set(self.tree[ls_path]) - (paths_to_request.union(ls, verified_paths)))
        
        response = []
        if ls:
            response.append('LS')
            if ls_path:
                response.append('*' + path + ' '.join(get_entries(self.log.find(ls_path))))
            for path in ls:
                for cpath in self.tree[path]:
                    response.append('%s %s' % (cpath, hex(self.merkle[cpath])[2:]))
        if entries_to_request:
            response.append('E-REQ')
            response.extend(entries_to_request)
        if paths_to_request:
            response.append('P-REQ')
            response.extend(paths_to_request)
        if not response:
            close = True
        if entries_to_send or paths_to_send:
            response.append('ENTRIES')
            for ehash in entries_to_send:
                response.append(self.log.entries[ehash].encode())
            for path in paths_to_send:
                for entry in get_entries(self.log.find(path)):
                    response.append(self.log.encode(entry))
        if close:
            response.append('CLOSE')
        response = '\n'.join(response)
        self.transport.write(response.encode())
    
#    def connection_lost(self, exc):
#        """
#        Called when the connection is lost or closed.
#        The argument is an exception object or None (the latter
#        meaning a regular EOF is received or the connection was
#        aborted or closed).
#        """
#        print("Connection lost! Closing server...")
#        self.server.close()

    def update_merkle(self, entry):
        hash = int(entry.hash, 16)
        path = os.sep
        for part in itertools.chain(entry.path.split(os.sep)):
            path = os.path.join(path, part)
            try:
                self.merkle[path] ^= hash
            except KeyError:
                self.merkle[path] = hash
                if os.path.dirname(path) != path:
                    self.tree[os.path.dirname(path)].append(path)
    
    def get_member(self):
        return '127.0.0.1'
        members = self.serf.members()
        members = members.body[b'Members']
        random.shuffle(members)
        myself = socket.gethostname()
        for member in members:
            if member[b'Status'] == b'alive' and member[b'Name'] != myself.encode():
                return member[b'Addr'].decode()
    
    def initial_request(self):
        request = [
            'LS',
            '%s %s' % (os.sep, hex(self.merkle[os.sep])[2:])
        ]
        return '\n'.join(request).encode()
    
    def initiate(self):
        print('initiate', 'connecting to', self.cport)
        ip = self.get_member()
        request = self.initial_request()
        reader, writer = yield from asyncio.open_connection(ip, self.cport)
        writer.write(request)
        writer.close()


@asyncio.coroutine
def do_full_sync(protocol):
    paths = None
    while True:
        print('do full sync')
        import random
        yield from asyncio.sleep(random.randint(1, 10))  # switch to other code and continue execution in 5 seconds
        yield from protocol.initiate()


def run(logpath, port):
    log = Log(logpath)
    log.load()
    view = View(log)
    view.build()
    node = view.get('/.cluster')
    del view
    ips = [line.strip() for line in node.entry.content.splitlines() if line.strip()]
    serf = SerfClient(log)
    result = serf.join(ips)
    if result.head[b'Error']:
        raise RuntimeError("Couldn't connect to serf cluster.")
    
    loop = asyncio.get_event_loop()
    cport = 2222 if port == 2223 else 2223
    protocol = FullSyncProtocol(log, port)
    protocol_factory = lambda: protocol
    print('server on', cport)
    server = loop.run_until_complete(loop.create_server(protocol_factory, 'localhost', cport))
    asyncio.async(do_full_sync(protocol))
    try:
        loop.run_until_complete(server.wait_closed())
    finally:
        loop.close()
#        loop.run_forever()
#    finally:
#        loop.close()
