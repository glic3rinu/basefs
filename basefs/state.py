import time
import collections

from . import utils, settings


class BlockState:
    """
    Maintanis state about Receiving, Stalled and Completed entries
    """
    RECEIVING = 'RECEIVING'
    STALLED = 'STALLED'
    COMPLETED = 'COMPLETED'
    
    def __init__(self, log):
        self.post_change = utils.Signal()
        self.log = log
        self.buffer = utils.LRUCache(settings.BLOCK_RECEIVING_BUFFER)
        self.incomplete = collections.defaultdict(list)
        for entry in self.log.entries.values():
            if entry.action == entry.WRITE and entry.next_block:
                self.incomplete[entry.next_block].append(entry)
        self.receiving = {}
    
    def iterate(self, entry, next_hash):
        while next_hash:
            try:
                block = self.buffer.pop(next_hash)
            except KeyError:
                try:
                    block = self.log.blocks[next_hash]
                except KeyError:
                    break
            else:
                block.save()
                block.log.add_block(block)
            next_hash = block.next_hash
        entry.next_block = next_hash
    
    def entry_received(self, entry):
        # already been validated
        if entry.action == entry.WRITE:
            self.iterate(entry, entry.content)
            if not entry.next_block:
                self.post_change.send(entry, self.RECEIVING, self.COMPLETED)
            else:
                self.incomplete[entry.next_block].append(entry)
                self.set_receiving(entry.hash)
    
    def block_received(self, block):
        entries = self.incomplete.pop(block.hash, [])
        if entries:
            block.save()
            block.log.add_block(block)
            prev_states = [self.get_state(entry.hash) for entry in entries]
            entry = entries[0]
            self.iterate(entry, block.next_hash)
            for entry, prev_state in zip(entries, prev_states):
                entry.next_block = entry.next_block
                if entry.next_block:
                    # Still receiving
                    self.incomplete[entry.next_block].append(entry)
                    self.set_receiving(entry.hash)
                    if prev_state != self.RECEIVING:
                        self.post_change.send(entry, prev_state, self.RECEIVING)
                else:
                    # Completed
                    self.receiving.pop(entry.hash)
                    self.post_change.send(entry, prev_state, self.COMPLETED)
        else:
            self.buffer.set(block.hash, block)
    
    def get_state(self, ehash):
        state = self.receiving.get(ehash, None)
        if state:
            timestamp, __ = state
            if timestamp+settings.BLOCK_RECEIVING_TIMEOUT >= time.time():
                return self.RECEIVING
            else:
                self.receiving.pop(ehash)
        entry = self.log.entries[ehash]
        if entry.next_block is None:
            return self.COMPLETED
        return self.STALLED
    
    def set_receiving(self, ehash):
        try:
            state = self.receiving[ehash]
        except KeyError:
            self.receiving[ehash] = [time.time(), 1]
        else:
            state[0], state[1] = time.time(), state[1]+1
    
    def get_receiving(self):
        now = time.time()
        receiving = list(self.receiving.items())
        for ehash, state in receiving:
            timestamp, __ = state
            if timestamp+settings.BLOCK_RECEIVING_TIMEOUT < now:
                # stalled
                self.receiving.pop(ehash)
                entry = self.log.entries[ehash]
                self.post_change.send(entry, self.RECEIVING, self.STALLED)
            else:
                yield ehash
