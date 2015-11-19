import asyncio
import functools
import itertools
import os
import random
from collections import defaultdict

from . import exceptions, signals, utils
from .messages import BlockState


def get_entries(entry, eq_path=False):
    # TODO
    yield entry
    for child in entry.childs:
        if not eq_path or entry.action in (entry.GRANT, entry.REVOKE) or child.name == entry.name:
            yield from get_entries(child)


def merkle_update_on_blockstate_change_factory(sync):
    def update_merkle(entry, pre, post, sync=sync):
        """
        Receiving:  No hash
        Completed:  Entry hash
        Stalled:    Entry hash and last block hash
               +-----------+       ehash
        [i]--->| Receiving +------------+
               +---+-------+            |
                   |   ^          +-----v-----+
             bhash |   | bhash    | Completed |
             ehash |   | ehash    +-----------+
                   v   |                ^
                +------+--+       bhash |
                | Stalled +-------------+
                +---------+
        """
        if BlockState.RECEIVING in (pre, post) and BlockState.STALLED in (pre, post):
            sync.update_merkle(entry)
            sync.update_merkle(entry, hash=entry.content)
        if post == BlockState.COMPLETED:
            if pre == BlockState.STALLED:
                sync.update_merkle(entry, hash=entry.content)
            if pre == BlockState.RECEIVING:
                sync.update_merkle(entry)
    return update_merkle


class SyncHandler:
    LS = 'LS'
    ENTRY_REQ = 'E-REQ'
    PATH_REQ = 'P-REQ'
    ENTRIES = 'ENTRIES'
    CLOSE = 'CLOSE'
    BLOCKS = 'BLOCKS'
    BLOCKS_REC = 'B-REC'
    BLOCK_REQ = 'B-REQ'
    SECTIONS = (BLOCKS_REC, LS, ENTRY_REQ, BLOCK_REQ, PATH_REQ, ENTRIES, BLOCKS, CLOSE)
    
    def __init__(self, view, serf):
        super().__init__()
        self.view = view
        self.serf = serf
        self.log = view.log
        self.merkle = {}
        self.tree = defaultdict(list)
        for entry in view.log.entries.values():
            self.update_merkle(entry)
            if entry.action == entry.WRITE and entry.next_block:
                # Stalled
                self.update_merkle(entry, hash=entry.content)
        self.log.post_create.connect(lambda e: self.update_merkle(e))
        serf.blockstate.post_change.connect(merkle_update_on_blockstate_change_factory(self))
        serf.received.connect(lambda e: e.action != e.WRITE and self.update_merkle(e))
    
    def update_merkle(self, entry, hash=None):
        if hash is None:
            hash = entry.hash
        hash = int(hash, 16)
        path = os.sep
        for part in itertools.chain(entry.path.split(os.sep)):
            path = os.path.join(path, part)
            try:
                self.merkle[path] ^= hash
            except KeyError:
                self.merkle[path] = hash
                if os.path.dirname(path) != path:
                    self.tree[os.path.dirname(path)].append(path)
    
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
    
    def data_received(self, transport, data):
        # TODO create a timer ???
        state = self.read_sync(transport, data)
        if state is not None:
            self.respond_sync(transport, state)
    
    def read_sync(self, transport, data):
        print('>>>>REQUEST<<<<<\n', data.decode())
        print('>>>><<<<')
        lines = self.decode(data).splitlines()
        entries_to_send = utils.OrderedSet()
        entries_to_request = utils.OrderedSet()
        blocks_to_send = utils.OrderedSet()
        blocks_to_request = utils.OrderedSet()
        paths_to_send = utils.OrderedSet()
        paths_to_request = utils.OrderedSet()
        verified_paths = utils.OrderedSet()
        receiving_blocks = defaultdict(list)
        ls = utils.OrderedSet()
        ls_paths = []
        for line in lines:
            if line in self.SECTIONS:
                section = line
                continue
            if section == self.BLOCKS_REC:
                path, *block_hashes = line.split()
                receiving_blocks[path].extend(block_hashes)
            elif section == self.LS:
                line = line.split()
                if line[0].startswith('*'):
                    # path entries
                    ls_path, rentries = line[0], set(line[1:])
                    ls_path = ls_path[1:]
                    ls_paths.append(ls_path)
                    ls_entry = self.log.find(ls_path)
                    lentries = utils.OrderedSet([lentry.hash for lentry in get_entries(ls_entry, eq_path=True)])
                    entries_to_send = entries_to_send.union(lentries - rentries)
                    entries_to_request = entries_to_request.union(rentries - lentries)
                elif line[0].startswith('!'):
                    b_path, rblocks = line[0], utils.OrderedSet(line[1:])
                    b_path = b_path[1:]
                    if b_path != ls_path:
                        raise RuntimeError("%s != %s" % (b_path, ls_path))
                    # Incomplete, non-receiving (remote or local), non-deleted blocks
                    lblocks = utils.OrderedSet()
                    for entry in get_entries(ls_entry, eq_path=True):
                        if entry.action == entry.WRITE:
                            # local/remove Non-receiving blocks
                            if (entry.hash not in receiving_blocks[entry.path] and
                                self.state.get_state(entry.hash) != self.state.RECEIVING):
                                # Incomplete
                                if entry.next_block:
                                    lblocks.add(entry.next_block)
                    blocks_to_send = blocks_to_send.union(lblocks - rblocks)
                    blocks_to_request = blocks_to_request.union(rblocks, lblocks)
                else:
                    # TODO Account for receiving entries
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
            elif section == self.ENTRY_REQ:
                entries_to_send.add(line)
            elif section == self.BLOCK_REQ:
                blocks_to_send.add(line)
            elif section == self.PATH_REQ:
                paths_to_send.add(line)
            elif section == self.ENTRIES:
                entry = self.decode_entry(line)
                try:
                    entry.clean()
                    entry.validate()
                except (exceptions.ValidationError, exceptions.Exists):
                    pass
                else:
                    self.log.add_entry(entry)
                    entry.save()
                    self.update_merkle(entry)
            elif section == self.BLOCKS:
                block = self.decode_block(line)
                try:
                    block.clean()
                    block.validate()
                except (exceptions.ValidationError, exceptions.Exists):
                    pass
                else:
                    if block.entry.hash not in self.receiving:
                        self.receiving[block.entry.hash] = block.entry
                        # Remove hash from merkle by reapling
                        self.update_merkle(entry.entry.last_next_block)
                    if block.is_last:
                        self.receiving.pop(block.entry.hash)
                    self.log.add_block(block)
                    block.save()
        if ls_paths:
            local_paths = []
            for ls_path in ls_paths:
                local_paths.extend(self.tree[ls_path])
            local_paths = utils.OrderedSet(local_paths)
            remote_paths = paths_to_request.union(ls, verified_paths)
            paths_to_send = paths_to_send.union(local_paths - remote_paths)
        for path in paths_to_send:
            for entry in get_entries(self.log.find(path)):
                entries_to_send.add(entry.hash)
                # TODO if non-receiving(remote or local), non-deleted blocks
                if entry.action == entry.WRITE:
                    blocks_to_send.add(entry.content)
        if section == self.CLOSE:
            transport.close()
            return
        return entries_to_send, entries_to_request, blocks_to_send, blocks_to_request, paths_to_request, ls
    
    def get_receiving(self):
        return [self.log.entries[ehash] for ehash in self.serf.blockstate.get_receiving()]
    
    def respond_sync(self, transport, state):
        entries_to_send, entries_to_request, blocks_to_send, blocks_to_request, paths_to_request, ls = state
        close = False
        response = []
        if ls:
            response.append(self.LS)
            receiving = defaultdict(list)
            receiving_entries = self.get_receiving()
            for path in ls:
                for entry in receiving_entries:
                    if utils.issubdir(path, entry.path):
                        receiving[entry.path].append(entry.hash)
                ls_entries = get_entries(self.log.find(path), eq_path=True)
                ls_ehashes = [entry.hash for entry in ls_entries]
                # * indicates all path hashes
                response.append('*%s ' % path + ' '.join(ls_ehashes))
                # TODO this doesn't acctually work
                incomplete_blocks = []
                for entry in ls_entries:
                    if entry.action == entry.WRITE and entry.last_next:
                        incomplete_blocks.append(entry.last_next)
                if path in incomplete_blocks:
                    response.append('!%s ' % path + ' '.join(incomplete_blocks))
                for cpath in self.tree[path]:
                    response.append('%s %s' % (cpath, hex(self.merkle[cpath])[2:]))
            if receiving:
                response.insert(0, self.BLOCKS_REC)
                for ix, recv in enumerate(receiving.items()):
                    path, hashes = recv
                    hashes = ' '.join(hashes)
                    response.insert(ix+1, "%s %s" % (path, hashes))
        if entries_to_request:
            response.append(self.ENTRY_REQ)
            response.extend(entries_to_request)
        if paths_to_request:
            response.append(self.PATH_REQ)
            response.extend(paths_to_request)
        if not response:
            close = True
        if entries_to_send:
            response.append(self.ENTRIES)
            for ehash in entries_to_send:
                response.append(self.encode_entry(self.log.entries[ehash]))
        if close:
            response.append(self.CLOSE)
        response = '\n'.join(response)
        print('>>>>RESPONSE<<<<<\n', self.encode(response).decode())
        print('>>>><<<<')
        transport.write(self.encode(response))
        if close:
            transport.close()
    
    def initial_request(self):
        request = []
        receiving = list(self.serf.blockstate.get_receiving())
        if receiving:
            request.append(self.BLOCKS_REC)
            for ehash in receiving:
                entry = self.log.entries[ehash]
                request.append('%s %s' % (entry.path, entry.content))
        request.append(self.LS)
        request.append('%s %s' % (os.sep, hex(self.merkle[os.sep])[2:]))
        return self.encode('\n'.join(request))


@asyncio.coroutine
def do_full_sync(client_factory, serf, period=5):
    loop = asyncio.get_event_loop()
    while True:
        yield from asyncio.sleep(period)
        member = serf.get_random_member()
        # TODO don't make sync requests with members that which whom we're already syncing
        if member:
            ip, port = member
            coro = loop.create_connection(client_factory, ip, port)
            asyncio.async(coro)
