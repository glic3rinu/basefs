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


@asyncio.coroutine
def sync_server(log, merkle, tree, port):
    # Start a socket server, call back for each client connected.
    # The client_connected_handler coroutine will be automatically converted to a Task
    yield from asyncio.start_server(functools.partial(client_connected_handler, log, merkle, tree), 'localhost', port)


@asyncio.coroutine
def client_connected_handler(log, merkle, tree, client_reader, client_writer):
    # Runs for each client connected
    # client_reader is a StreamReader object
    # client_writer is a StreamWriter object
    print("Connection received!")
    print('aaaaaaaaaaaaaaaaaaaaaaaaa', merkle)
    while True:
        data = yield from client_reader.read(8192)
        if not data:
            break
        print(data)
        lines = data.decode().splitlines()
        print('l', lines)
        if lines[0] == 'SYNCREQ':
            print('received syinc')
            for line in lines[1:]:
                path, hash = line.split()
                try:
                    local_hash = merkle[path]
                except KeyError:
                    print('SHIT', str(merkle), path)
                else:
                    if hex(local_hash)[2:] == hash:
                        print('GOOD %s' % path)
                    else:
                        print('BAD %s %s %s' % (path, hash, hex(local_hash)[2:]))
        print('aa', data)
        client_writer.write(data)


@asyncio.coroutine
def send_periodically(serf):
    while True:
        yield from asyncio.sleep(1)  # switch to other code and continue execution in 5 seconds
        print('> Periodic event happened.')
        print(serf.members())

EOF = 'EOF'
@asyncio.coroutine
def do_full_sync(serf, log, merkle, tree, port):
    while True:
        print('aaaaaaaaaaaaaaaaaaaaaaaaa', merkle)
        print('eeeeeeeeeeeeeeeeeeeeeeeee', tree)
        yield from asyncio.sleep(5)  # switch to other code and continue execution in 5 seconds
        members = serf.members()
        members = members.body[b'Members']
        import random
        random.shuffle(members)
        print(dir(serf))
        print(serf.host)
        print(members)
        import socket
        
        myself = socket.gethostname()
        for member in members:
            if member[b'Status'] == b'alive' and member[b'Name'] != myself.encode():
                do_full_sync(member[b'Addr'].decode(), log, merkle, tree)
                break
    #        Port': 7946,
    #        Addr': b'
        ip = 'localhost'
        print(tree, merkle)
        merkle_tree = print_merkle(merkle, tree)
        # Open a connection and write a few lines by using the StreamWriter object
        reader, writer = yield from asyncio.open_connection(ip, port)
        # reader is a StreamReader object
        # writer is a StreamWriter object
        
        
        writer.write(b'SYNCREQ\n')
        print(merkle_tree.encode())
        writer.write(merkle_tree.encode())
     
        # Now, read a few lines by using the StreamReader object
        print("Lines received")
#        while True:
#            line = yield from reader.readline()
#            print(line)
#            if line == EOF or not line:
#                break
#        writer.close()


def print_merkle(merkle, tree, path=os.sep):
    ret = '%s %s\n' % (path, hex(merkle[path])[2:])
    for child_path in tree[path]:
        ret += print_merkle(merkle, tree, child_path)
    return ret


def update_merkle(merkle, tree, entry):
    hash = int(entry.hash, 16)
    path = os.sep
    for part in itertools.chain([''], entry.path.split(os.sep)):
        path = os.path.join(path, part)
        try:
            merkle[path] ^= hash
        except KeyError:
            merkle[path] = hash
            if os.path.dirname(path) != path:
                tree[os.path.dirname(path)].append(path)

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

    tree = defaultdict(list)
    merkle = {}
    for entry in log.entries.values():
        update_merkle(merkle, tree, entry)
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(sync_server(log, merkle, tree, port-1))
    asyncio.async(do_full_sync(serf, log, merkle, tree, port))
    try:
        loop.run_forever()
    finally:
        loop.close()
