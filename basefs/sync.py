import asyncio
import functools
import itertools
import logging
import os
import random
import time
import traceback
from collections import defaultdict

from . import exceptions, utils


logger = logging.getLogger('basefs.sync')


def get_entries(entry, eq_path=False):
    yield entry
    for child in entry.childs:
        if not eq_path or entry.action in (entry.GRANT, entry.REVOKE) or child.name == entry.name:
            yield from get_entries(child)


class SyncHandler:
    BLOCKS_REC = 'B-REC'
    HASH = 'HASH'
    LS = 'LS'
    ENTRY_REQ = 'E-REQ'
    PATH_REQ = 'P-REQ'
    ENTRIES = 'ENTRIES'
    CLOSE = 'CLOSE'
    BLOCKS = 'BLOCKS'
    BLOCK_REQ = 'B-REQ'
    SECTIONS = (HASH, BLOCKS_REC, LS, ENTRY_REQ, BLOCK_REQ, PATH_REQ, ENTRIES, BLOCKS, CLOSE)
    description = 'full sync'
    SEED_NODES = 4 # TODO configure
    members_state = {}
    
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
        self.log.post_create.connect(self.update_merkle)
        serf.blockstate.post_change.connect(self.blockstate_change)
        serf.entry_received.connect(lambda e: e.action != e.WRITE and self.update_merkle(e))
        self.syncing = set()
    
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
    
    def blockstate_change(self, entry, pre, post):
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
        [i]---->| Stalled +-------------+
                +---------+
        """
        assert pre != post
        blockstate = self.blockstate
        if blockstate.RECEIVING in (pre, post) and blockstate.STALLED in (pre, post):
            self.update_merkle(entry)
            self.update_merkle(entry, hash=entry.content)
        if post == blockstate.COMPLETED:
            if pre == blockstate.STALLED:
                self.update_merkle(entry, hash=entry.content)
            elif pre == blockstate.RECEIVING:
                self.update_merkle(entry)
    
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
        try:
            peername = writer.get_extra_info('peername')
            self.syncing.add(peername)
            self.members_state.get(peername, time.time())
            state = yield from self.read_sync(reader, writer)
            if state is not None:
                state = yield from self.respond_sync(reader, writer, state)
                if state:
                    yield from self.data_received(reader, writer)
        finally:
            self.close(writer)
    
    def split(self, line):
        """ path aware """
        path, *tail = line.split()
        while path[-1] == '\\':
            path = path[:-1] + ' ' + tail[0]
            tail = tail[1:]
        tail.insert(0, path)
        return tail
    
    def close(self, writer):
        peername = writer.get_extra_info('peername')
        if peername in self.syncing:
            self.syncing.remove(peername)
        writer.close()
        logger.debug("Closed full sync with %s" % str(peername))
    
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
        for entry in self.get_and_update_receiving():
            lreceiving[entry.path].append(entry.hash)
        ls = utils.OrderedSet()
        ls_paths = []
        b_path = None
        line = yield from reader.readline()
        if not line:
            return
        while line and line != b'EOF\n':
            line = line.decode().rstrip('\n')
            logger.debug('R: %s', line)
            if line in self.SECTIONS:
                section = line
                line = yield from reader.readline()
                continue
            if section == self.HASH:
                if self.log.root.hash != line:
                    self.write(writer, self.CLOSE)
                    self.write(writer, 'Filesystem hash does not match %s != %s' % (self.log.root.hash, line))
                    self.close(writer)
                    return
            elif section == self.BLOCKS_REC:
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
                    lentries = utils.OrderedSet()
                    try:
                        ls_entry = self.log.find(ls_path)
                    except exceptions.DoesNotExit:
                        pass
                    else:
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
                if line in self.log.blocks:
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
            try:
                lentry = self.log.find(path)
            except exceptions.DoesNotExist:
                pass
            else:
                lentries = get_entries(lentry)
                for entry in lentries:
                    entries_to_send.add(entry.hash)
        if section == self.CLOSE:
            self.close(writer)
            return
        return entries_to_send, entries_to_request, blocks_to_send, blocks_to_request, paths_to_request, ls, lreceiving
    
    def get_and_update_receiving(self):
        return [self.log.entries[ehash] for ehash in self.blockstate.get_and_update_receiving()]
    
    def write(self, writer, line):
        if isinstance(line, str):
            line = line.encode()
        logger.debug('W: %s', line.decode())
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
                try:
                    lentry = self.log.find(path)
                except exceptions.DoesNotExist:
                    ls_entries = []
                else:
                    ls_entries = list(get_entries(lentry, eq_path=True))
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
                yield from writer.drain()
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
                yield from writer.drain()
        if blocks_to_send:
            self.write(writer, self.BLOCKS)
            sent_blocks = set()
            for bhash in blocks_to_send:
                next = self.log.blocks[bhash]
                while next:
                    if next.hash in sent_blocks:
                        break
                    self.write(writer, self.encode_block(next))
                    yield from writer.drain()
                    sent_blocks.add(next.hash)
                    try:
                        next = next.next
                    except KeyError:
                        next = None
        if close:
            self.write(writer, self.CLOSE)
            self.close(writer)
        else:
            self.write(writer, 'EOF')
            return True
    
    def get_random_members(self, init=time.time(), num=1):
        """ Time-biased, older more probable """
        members = self.serf.members(status=b'alive')
        now = time.time()
        total = 0
        choices = []
        for member in members.body[b'Members']:
            if member[b'Name'] != self.serf.hostname.encode():
                member = (member[b'Addr'].decode(), member[b'Port']+2)
                if member in self.syncing:
                    continue
                weight = now - self.members_state.get(member, init)
                choices.append((member, weight))
                total += weight
        result = []
        while choices and len(result) < num:
            r = random.uniform(0, total)
            for c, w in list(choices):
                r -= w
                if r < 0:
                    result.append(c)
                    choices.remove((c, w))
                    break
        logger.debug("Get random members, syncing: %i, choices: %i, results: %i" % (
            len(self.syncing), len(choices), len(result)
        ))
        return result
    
    @asyncio.coroutine
    def initial_request(self, reader, writer):
        peername = writer.get_extra_info('peername')
        logger.debug('Initiating sync with %s', str(peername))
        receiving = self.get_and_update_receiving()
        writer.write(b's')
        # TODO replace self.HASH by self.ID
        self.write(writer, self.HASH)
        self.write(writer, self.log.root.hash)
        if receiving:
            self.write(writer, self.BLOCKS_REC)
            for entry in receiving:
                self.write(writer, '%s %s' % (entry.path.replace(' ', '\ '), entry.hash))
        self.write(writer, self.LS)
        self.write(writer, '%s %s' % (os.sep, hex(self.merkle[os.sep])[2:]))
        self.write(writer, 'EOF')
        yield from self.data_received(reader, writer)


@asyncio.coroutine
def do_full_sync(sync, config=None):
    loop = asyncio.get_event_loop()
    
    @asyncio.coroutine
    def full_sync(members):
        for member in members:
            retries = 4
            while retries:
                ip, port = member
                logger.debug("Open connection with %s:%s" % (ip, port))
                try:
                    reader, writer = yield from asyncio.open_connection(ip, port, loop=loop)
                except TimeoutError:
                    retries -= 1
                    logger.error("Connection timed out contacting %s:%s, %i retries left" % (ip, port, retries))
                    yield from asyncio.sleep(1)
                except OSError:
                    retries -= 1
                    logger.error("Connect call failed contacting %s:%s, %i retries left" % (ip, port, retries))
                    yield from asyncio.sleep(1)
                else:
                    yield from sync.initial_request(reader, writer)
                    break
    
    @asyncio.coroutine
    def seed_sync():
        yield from asyncio.sleep(0.2)
        members = sync.f_members(num=sync.SEED_NODES)
        logger.debug('Seeding to %s', members)
        try:
            yield from full_sync(members)
        except Exception as exc:
            logger.error(traceback.format_exc())
    sync.serf.partial_gossip.connect(lambda: loop.call_soon_threadsafe(asyncio.async, seed_sync()))
    
    FULL_SYNC_INTERVAL = 20
    if config:
        FULL_SYNC_INTERVAL = int(config.get('full_sync_interval', FULL_SYNC_INTERVAL))
    deviation = int(FULL_SYNC_INTERVAL*0.1)
    FULL_SYNC_INTERVAL = (FULL_SYNC_INTERVAL-deviation, FULL_SYNC_INTERVAL+deviation)
    while True:
        try:
            seconds = random.randint(*FULL_SYNC_INTERVAL)
            logger.info("Next full sync in %i seconds" % seconds)
            yield from asyncio.sleep(seconds)
            members = sync.get_random_members(num=1)
            if not members:
                logger.warning("No members available for full state synchronization.")
            yield from full_sync(members)
        except Exception as exc:
            logger.error(traceback.format_exc())
