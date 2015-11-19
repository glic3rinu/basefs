import binascii
import random
import struct
import sys
import time
import zlib

from serfclient import client

from basefs import utils, exceptions
from basefs.logs import LogEntry, Block


class SerfClient(client.SerfClient):
    ACTION_MAP = {
        LogEntry.WRITE: 'W',
        LogEntry.MKDIR: 'M',
        LogEntry.DELETE: 'D',
        LogEntry.GRANT: 'G',
        LogEntry.REVOKE: 'R',
        LogEntry.SLINK: 'S',
        LogEntry.LINK: 'L',
        LogEntry.REVERT: 'E',
        LogEntry.MODE: 'O',
        LogEntry.ACK: 'A',
    }
    ACTION_REVERSE_MAP = {v: k for k, v in ACTION_MAP.items()}
    
    def __init__(self, log, *args, **kwargs):
        self.log = log
        self.block_buffer = utils.LRUCache(2048)
        self.incomplete = {}
        self.blockstate = BlockState(log)
        self.received = utils.Signal()
        for entry in log.entries.values():
            if entry.action == entry.WRITE and entry.next_block:
                self.incomplete[entry.next_block] = entry.hash
        super().__init__(*args, **kwargs)
    
    def join(self, location):
        """
        Join another cluster by provided a list of ip:port locations.
        """
        if not isinstance(location, (list, tuple)):
            location = [location]
        req = {
            'Existing': location,
            'Replay': True
        }
        return self.connection.call('join', req)
    
    def stats(self):
        """
        Force a node to leave the cluster.
        """
        return self.connection.call('stats')
    
    @property
    def hostname(self):
        if not hasattr(self, '_hostname'):
            stats = self.stats()
            self._hostname = stats.body[b'agent'][b'name'].decode()
        return self._hostname
    
    def get_random_member(self):
        members = self.members(status=b'alive')
        members = members.body[b'Members']
        random.shuffle(members)
        for member in members:
            if member[b'Name'] != self.hostname.encode():
                return member[b'Addr'].decode(), member[b'Port']+2
    
    def encode(self, entry):
        if isinstance(entry, LogEntry):
            parent_hash = binascii.a2b_hex(entry.parent_hash)
            timestamp = struct.pack('>I', entry.timestamp)
            action = self.ACTION_MAP[entry.action].encode()
            name = entry.name.encode()
            name_offset = struct.pack('B', len(name))
            content = entry.content
            if entry.action in (entry.WRITE, entry.LINK, entry.REVERT):
                content = binascii.a2b_hex(content)
            elif entry.action == entry.GRANT:
                content = content.to_der()
            elif entry.action == entry.MODE:
                content = struct.pack('>I', content)
            else:
                content = content.encode()
            content_offset = struct.pack('B', len(content))
            fingerprint = binascii.a2b_hex(entry.fingerprint.replace(':', ''))
            signature = entry.signature
            return b''.join((b'e', parent_hash, timestamp, action, name_offset, name,
                             content_offset, content, fingerprint, signature))
        elif isinstance(entry, Block):
            block = entry
            next_hash = binascii.a2b_hex(block.next_hash if block.next_hash else '0'*56)
            return b''.join((b'b', next_hash, block.content))
    
    def decode(self, data, offset=0, entries=None):
        if entries is None:
            entries = []
        event = data[offset:offset+1].decode()
        offset += 1
        if event == 'e':
            parent_hash = binascii.b2a_hex(data[offset:offset+28]).decode()
            offset += 28
            timestamp = struct.unpack('>I', data[offset:offset+4])[0]
            offset += 4
            action = data[offset:offset+1].decode()
            action = self.ACTION_REVERSE_MAP[action]
            offset += 1
            name_offset = struct.unpack('B', data[offset:offset+1])[0]
            offset += 1
            name = data[offset:offset+name_offset].decode()
            offset += name_offset
            content_offset = struct.unpack('B', data[offset:offset+1])[0]
            offset += 1
            content = data[offset:offset+content_offset]
            if action in (LogEntry.WRITE, LogEntry.LINK, LogEntry.REVERT):
                content = binascii.b2a_hex(content)
            elif action == LogEntry.GRANT:
                content = Key.from_der(content)
            elif action == LogEntry.MODE:
                content = struct.unpack('>I', content)[0]
            content = content.decode()
            offset += content_offset
            fingerprint = binascii.b2a_hex(data[offset:offset+16]).decode()
            fingerprint = ':'.join(a+b for a,b in zip(fingerprint[::2], fingerprint[1::2]))
            offset += 16
            signature =  data[offset:offset+48]
            offset += 48
            entry = LogEntry(self.log, parent_hash, action, name, content,
                timestamp=timestamp, fingerprint=fingerprint, signature=signature)
            entries.append(entry)
        elif event == 'b':
            next_hash = binascii.b2a_hex(data[offset:offset+28]).decode()
            if next_hash == '0'*56:
                next_hash = None
            offset += 28
            content = data[offset:]
            offset += len(content)
            block = Block(self.log, next_hash, content)
            entries.append(block)
        else:
            raise ValueError("Unknown token '%s', data:'%s'" % (event, data))
        if len(data) > offset:
            self.decode(data, offset, entries)
        return entries
    
    def send(self, *entries):
        data = b''
        for entry in entries:
            entry_data = self.encode(entry)
            if len(data) + len(entry_data) > 512:
                event = chr(data[0])
                self.event(event, data[1:], coalesce=False)
                data = entry_data
            else:
                data += entry_data
            if entry.action == entry.WRITE:
                for block in entry.get_blocks():
                    block_data = self.encode(block)
                    if len(data) + len(block_data) > 512:
                        event = chr(data[0])
                        self.event(event, data[1:], coalesce=False)
                        data = block_data
                    else:
                        data += block_data
        if data:
            event = chr(data[0])
            self.event(event, data[1:], coalesce=False)
    
    def data_received(self, transport, data):
        entries = self.decode(data[:-1]) # remove \n char inserted by serf
        for entry in entries:
            if isinstance(entry, LogEntry):
                try:
                    entry.clean()
                except exceptions.Exists:
                    continue
                entry.validate()
                entry.save()
                self.log.add_entry(entry)
                self.received.send(entry)
                if entry.action == entry.WRITE:
                    next_hash = entry.content
                    while next_hash:
                        try:
                            block = self.block_buffer.pop(next_hash)
                        except KeyError:
                            self.incomplete[next_hash] = entry.hash
                            self.blockstate.set_receiving(entry.hash)
                            break
                        else:
                            block.save()
                            block.log.add_block(block)
                            next_hash = block.next_hash
                    else:
                        self.blockstate.post_change.send(entry, self.blockstate.RECEIVING, self.blockstate.COMPLETED)
                
            else:
                # Block
                block = entry
                ehash = self.incomplete.pop(block.hash, None)
                if ehash:
                    prev_state = self.blockstate.get_state(ehash)
                    try:
                        block.clean()
                    except exceptions.Exists:
                        pass
                    else:
                        block.save()
                        block.log.add_block(block)
                        while block.next_hash:
                            try:
                                block = self.block_buffer.pop(block.next_hash)
                            except KeyError:
                                break
                            else:
                                block.save()
                                block.log.add_block(block)
                    if block.next_hash:
                        # Still receiving
                        self.incomplete[block.next_hash] = ehash
                        if prev_state != self.blockstate.RECEIVING:
                            entry = self.log.entries[ehash]
                            self.blockstate.post_change.send(entry, prev_state, self.blockstate.RECEIVING)
                    else:
                        # Completed
                        self.blockstate.receiving.pop(ehash, None)
                        entry = self.log.entries[ehash]
                        entry.next_block = None
                        self.blockstate.post_change.send(entry, prev_state, self.blockstate.COMPLETED)
                else:
                    self.block_buffer.set(block.hash, block)
        transport.close()


class BlockState:
    RECEIVING = 'R'
    STALLED = 'S'
    COMPLETED = 'C'
    
    def __init__(self, log):
        self.log = log
        self.post_change = utils.Signal()
        self.receiving = {}
    
    def get_state(self, ehash):
        if self.receiving.get(ehash, None):
            return self.RECEIVING
        entry = self.log.entries[ehash]
        if entry.is_complete:
            return self.COMPLETED
        return self.STALLED
    
    def set_receiving(self, ehash):
        self.receiving[ehash] = time.time()
    
    def get_receiving(self):
        now = time.time()
        receiving = list(self.receiving.items())
        for ehash, timestamp in receiving:
            if timestamp+60 < now:
                # stalled
                self.receiving.pop(ehash)
                entry = self.log.entries[ehash]
                self.post_change.send(entry, self.RECEIVING, self.STALLED)
            else:
                yield ehash
