import asyncio
import functools
import itertools
import logging
import os
import random
import traceback
from collections import defaultdict

from . import exceptions, signals, utils, settings


logger = logging.getLogger('basefs.sync')


def get_entries(entry, eq_path=False):
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
        self.serf = serf
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
        self.responses = {}
    
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
    
    def encode_entry(self, entry):
        # TODO remove unthrosworthy shit (hash) and whatever
        return self.log.encode(entry)
    
    def decode_entry(self, line):
        return self.log.decode(line)
    
    def encode_block(self, block):
        return self.log.encode(block)
    
    def decode_block(self, block):
        return self.log.decode(block)
    
    @asyncio.coroutine
    def data_received(self, reader, writer, *token):
        state = yield from self.read_sync(reader, writer)
        if state is not None:
            state = yield from self.respond_sync(reader, writer, state)
            if state:
                yield from self.data_received(reader, writer)
        writer.close()
    
    def split(self, line):
        """ path aware """
        path, *tail = line.split()
        while path[-1] == '\\':
            path = path[:-1] + ' ' + tail[0]
            tail = tail[1:]
        tail.insert(0, path)
        return tail
    
    @asyncio.coroutine
    def read_sync(self, reader, writer):
        entries_to_send = utils.OrderedSet()
        entries_to_request = utils.OrderedSet()
        blocks_to_send = utils.OrderedSet()
        blocks_to_request = utils.OrderedSet()
        paths_to_send = utils.OrderedSet()
        paths_to_request = utils.OrderedSet()
        verified_paths = utils.OrderedSet()
        rreceiving = defaultdict(list)
        lreceiving = defaultdict(list)
        for entry in self.get_receiving():
            lreceiving[entry.path].append(entry.hash)
        ls = utils.OrderedSet()
        ls_paths = []
        b_path = None
        line = yield from reader.readline()
        if not line:
            return
        while line and line != b'EOF\n':
            print('R', line)
            line = line.decode().rstrip('\n')
            if line in self.SECTIONS:
                section = line
                line = yield from reader.readline()
                continue
            if section == self.BLOCKS_REC:
                path, *entries_hashes = self.split(line)
                rreceiving[path].extend(entries_hashes)
            elif section == self.LS:
                line = self.split(line)
                # TODO account for receiving???
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
                    path, rhash = line
                    try:
                        lhash = self.merkle[path]
                    except KeyError:
                        paths_to_request.add(path)
                    else:
                        # apply receiving entries (local and remote)
                        lrec, rrec = set(), set()
                        for lpath, ehashes in lreceiving.items():
                            if utils.issubdir(lpath, path):
                                [lrec.add(ehash) for ehash in ehashes]
                        for rpath, ehashes in rreceiving.items():
                            if utils.issubdir(rpath, path):
                                [lrec.add(ehash) for ehash in ehashes]
                        for rrechash in rrec-lrec:
                            lhash ^= int(rrechash, 16)
                        rhash = int(rhash, 16)
                        for lrechash in lrec-rrec:
                            rhash ^= int(lrechash, 16)
                        if lhash != rhash:
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
            line = yield from reader.readline()
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
            writer.close()
            return
        return entries_to_send, entries_to_request, blocks_to_send, blocks_to_request, paths_to_request, ls, lreceiving
    
    def get_receiving(self):
        return [self.log.entries[ehash] for ehash in self.blockstate.get_receiving()]
    
    def write(self, writer, line):
        if isinstance(line, str):
            line = line.encode()
        print('W', line)
        writer.write(line + b'\n')
    
    @asyncio.coroutine
    def respond_sync(self, reader, writer, state):
        entries_to_send, entries_to_request, blocks_to_send, blocks_to_request, paths_to_request, ls, lreceiving = state
        close = False
#        response = []
        if ls:
            receiving = {}
            for path in ls:
                for rpath, entries in lreceiving.items():
                    if utils.issubdir(rpath, path):
                        receiving[rpath] = entries
            if receiving:
                self.write(writer, self.BLOCKS_REC)
                for recv in receiving.items():
                    path, hashes = recv
                    hashes = ' '.join(hashes)
                    self.write(writer, "%s %s" % (path.replace(' ', '\ '), hashes))
            self.write(writer, self.LS)
            for path in ls:
                ls_entries = list(get_entries(self.log.find(path), eq_path=True))
                incomplete_blocks = []
                for entry in ls_entries:
                    if (entry.action == entry.WRITE and entry.next_block and
                        self.blockstate.get_state(entry.hash) != self.blockstate.RECEIVING):
                            incomplete_blocks.append(entry.next_block)
                # ! indicate incomplete stalled blocks
                if incomplete_blocks:
                    self.write(writer, '!%s %s' % (path.replace(' ', '\ '), ' '.join(incomplete_blocks)))
                ls_ehashes = [entry.hash for entry in ls_entries]
                # * indicates all path hashes
                self.write(writer, '*%s %s' % (path.replace(' ', '\ '), ' '.join(ls_ehashes)))
                for cpath in self.tree[path]:
                    self.write(writer, '%s %s' % (cpath.replace(' ', '\ '), hex(self.merkle[cpath])[2:]))
        if entries_to_request:
            self.write(writer, self.ENTRY_REQ)
            for line in entries_to_request:
                self.write(writer, line)
        if paths_to_request:
            self.write(writer, self.PATH_REQ)
            for line in paths_to_request:
                self.write(writer, line)
        if blocks_to_request:
            self.write(writer, self.BLOCK_REQ)
            for line in blocks_to_request:
                self.write(writer, line)
        if not (ls or entries_to_request or paths_to_request or blocks_to_request):
            close = True
        if entries_to_send:
            self.write(writer, self.ENTRIES)
            for ehash in entries_to_send:
                self.write(writer, self.encode_entry(self.log.entries[ehash]))
        if blocks_to_send:
            self.write(writer, self.BLOCKS)
            sent_blocks = set()
            for bhash in blocks_to_send:
                next = self.log.blocks[bhash]
                while next:
                    if next.hash in sent_blocks:
                        break
                    self.write(writer, self.encode_block(next))
                    sent_blocks.add(next.hash)
                    next = next.next
        if close:
            self.write(writer, self.CLOSE)
#            yield from writer.drain()
            writer.close()
        else:
            self.write(writer, 'EOF')
            return True
#            yield from writer.drain()
#        response = self.encode('\n'.join(response))
#        logger.debug('Responding: %s', response.decode())
#        transport.write(response)
#        if close:
#            transport.close()
    
    @asyncio.coroutine
    def initial_request(self, reader, writer):
        peername = writer.get_extra_info('peername')
        logger.debug('Initiating sync with %s', peername)
        receiving = list(self.blockstate.get_receiving())
        writer.write(b's')
        if receiving:
            self.write(writer, self.BLOCKS_REC)
            for ehash in receiving:
                entry = self.log.entries[ehash]
                self.write(writer, '%s %s' % (entry.path.replace(' ', '\ '), entry.hash))
        self.write(writer, self.LS)
        self.write(writer, '%s %s' % (os.sep, hex(self.merkle[os.sep])[2:]))
        self.write(writer, 'EOF')
#        yield from writer.drain()
        yield from self.data_received(reader, writer)


@asyncio.coroutine
def do_full_sync(sync):
    loop = asyncio.get_event_loop()
    while True:
        try:
            yield from asyncio.sleep(random.randint(*settings.FULL_SYNC_INTERVAL))
            member = sync.serf.get_random_member()
            # TODO don't make sync requests with members that which whom we're already syncing
            if member:
                ip, port = member
                reader, writer = yield from asyncio.open_connection(ip, port, loop=loop)
                yield from sync.initial_request(reader, writer)
        except Exception as exc:
            logger.error(traceback.format_exc())
