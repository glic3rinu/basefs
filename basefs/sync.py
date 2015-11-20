import asyncio
import functools
import itertools
import logging
import os
import random
from collections import defaultdict

from . import exceptions, signals, utils


logger = logging.getLogger('basefs.sync')


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
        blockstate = sync.blockstate
        if blockstate.RECEIVING in (pre, post) and blockstate.STALLED in (pre, post):
            sync.update_merkle(entry)
            sync.update_merkle(entry, hash=entry.content)
        if post == blockstate.COMPLETED:
            if pre == blockstate.STALLED:
                sync.update_merkle(entry, hash=entry.content)
            if pre == blockstate.RECEIVING:
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
    
    def __str__(self):
        return "Sync:%s" % self.log.logpath 
    
    def __init__(self, view, serf):
        super().__init__()
        self.view = view
        self.blockstate = serf.blockstate
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
        serf.entry_received.connect(lambda e: e.action != e.WRITE and self.update_merkle(e))
    
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
    
    def encode_block(self, block):
        return self.log.encode(block)
    
    def decode_block(self, block):
        return self.log.decode(block)
    
    def data_received(self, transport, data):
        # TODO create a timer ???
        state = self.read_sync(transport, data)
        if state is not None:
            self.respond_sync(transport, state)
    
    def read_sync(self, transport, data):
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
        b_path = None
        for line in lines:
            if line in self.SECTIONS:
                section = line
                continue
            if section == self.BLOCKS_REC:
                path, *entries_hashes = line.split()
                receiving_blocks[path].extend(entries_hashes)
            elif section == self.LS:
                line = line.split()
                if line[0].startswith('!'):
                    b_path, rblocks = line[0], utils.OrderedSet(line[1:])
                    b_path = b_path[1:]
                    for rblock in rblocks:
                        try:
                            rblock = self.log.blocks[rblock]
                        except KeyError:
                            pass
                        else:
                            blocks_to_send.add(rblock.hash)
                elif line[0].startswith('*'):
                    # path entries
                    ls_path, rentries = line[0], set(line[1:])
                    ls_path = ls_path[1:]
                    ls_paths.append(ls_path)
                    ls_entry = self.log.find(ls_path)
                    lentries = utils.OrderedSet()
                    for lentry in get_entries(ls_entry, eq_path=True):
                        lentries.add(lentry.hash)
                        if (lentry.action == lentry.WRITE and
                            lentry.next_block and (b_path is None or lentry.next_block not in rblocks) and
                            lentry.hash in rentries and
                            self.blockstate.get_state(lentry.hash) != self.blockstate.RECEIVING):
                                blocks_to_request.add(lentry.next_block)
                    entries_to_send = entries_to_send.union(lentries - rentries)
                    entries_to_request = entries_to_request.union(rentries - lentries)
                    b_path = None
                else:
                    # TODO Account for receiving entries (local and remote)
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
                    if entry.action != entry.WRITE:
                        self.update_merkle(entry)
                    self.blockstate.entry_received(entry)
            elif section == self.BLOCKS:
                block = self.decode_block(line)
                try:
                    block.clean()
                except (exceptions.ValidationError, exceptions.Exists):
                    pass
                else:
                    self.blockstate.block_received(block)
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
        if section == self.CLOSE:
            transport.close()
            return
        return entries_to_send, entries_to_request, blocks_to_send, blocks_to_request, paths_to_request, ls
    
    def get_receiving(self):
        return [self.log.entries[ehash] for ehash in self.blockstate.get_receiving()]
    
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
                ls_entries = list(get_entries(self.log.find(path), eq_path=True))
                incomplete_blocks = []
                for entry in ls_entries:
                    # TODO exclude receiving
                    if entry.action == entry.WRITE and entry.next_block:
                        incomplete_blocks.append(entry.next_block)
                # ! indicate incomplete blocks
                if path in incomplete_blocks:
                    response.append('!%s ' % path + ' '.join(incomplete_blocks))
                ls_ehashes = [entry.hash for entry in ls_entries]
                # * indicates all path hashes
                response.append('*%s ' % path + ' '.join(ls_ehashes))
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
        if blocks_to_request:
            response.append(self.BLOCK_REQ)
            response.extend(blocks_to_request)
        if not response:
            close = True
        if entries_to_send:
            response.append(self.ENTRIES)
            for ehash in entries_to_send:
                response.append(self.encode_entry(self.log.entries[ehash]))
        if blocks_to_send:
            response.append(self.BLOCKS)
            sent_blocks = set()
            for bhash in blocks_to_send:
                next = self.log.blocks[bhash]
                while next:
                    if next.hash in sent_blocks:
                        break
                    response.append(self.encode_block(next))
                    sent_blocks.add(next.hash)
                    next = next.next
        if close:
            response.append(self.CLOSE)
        response = self.encode('\n'.join(response))
        logger.debug('Responding: %s', response.decode())
        transport.write(response)
        if close:
            transport.close()
    
    def initial_request(self, transport):
        request = []
        receiving = list(self.blockstate.get_receiving())
        if receiving:
            request.append(self.BLOCKS_REC)
            for ehash in receiving:
                entry = self.log.entries[ehash]
                request.append('%s %s' % (entry.path, entry.hash))
        request.append(self.LS)
        request.append('%s %s' % (os.sep, hex(self.merkle[os.sep])[2:]))
        request = self.encode('\n'.join(request))
        logger.debug('Requesting: %s', request.decode())
        transport.write(request)


@asyncio.coroutine
def do_full_sync(client_factory, serf):
    loop = asyncio.get_event_loop()
    while True:
        yield from asyncio.sleep(105 or random.randint(5, 60))
        member = serf.get_random_member()
        # TODO don't make sync requests with members that which whom we're already syncing
        if member:
            ip, port = member
            coro = loop.create_connection(client_factory, ip, port)
            asyncio.async(coro)
