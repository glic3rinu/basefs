import binascii
import sys
import zlib

from serfclient import client

from basefs import utils, exceptions
from basefs.logs import LogEntry


class SerfClient(client.SerfClient):
#    ACTION_MAP = {
#        LogEntry.WRITE: 'W',
#        LogEntry.MKDIR: 'M',
#        LogEntry.DELETE: 'D',
#        LogEntry.GRANT: 'G',
#        LogEntry.REVOKE: 'R',
#    }
#    ACTION_REVERSE_MAP:
#        'W': LogEntry.WRITE,
#        'M': LogEntry.MKDIR,
#        'D': LogEntry.DELETE,
#        'G': LogEntry.GRANT,
#        'R': LogEntry.REVOKE,
#    }
    
    def __init__(self, log, *args, **kwargs):
        self.log = log
        super(SerfClient, self).__init__(*args, **kwargs)
    
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
    
    def send(self, entry):
        signature = binascii.b2a_base64(entry.signature).decode().rstrip()
#        action = self.ACTION_MAP[entry.action]
        line = ' '.join(map(str, (entry.parent_hash, entry.time, entry.fingerprint,
                                  action, entry.path, signature)))
        if entry.content:
            line += '\n' + entry.content
        line = zlib.compress(line.encode())
        if len(line) > 512:
            raise KeyError("Line too long %s" % len(line))
        self.event('logentry', line, coalesce=False)
    
    def receive(self, payload):
        sys.stderr.write('SIZE: %s\n' % len(payload))
        payload = zlib.decompress(payload).decode()
        lines = payload.split('\n')
        parent_hash, time, fingerprint, action, path, signature = lines[0].strip().split()
        
        content = '\n'.join(lines[1:])
        signature = binascii.a2b_base64(signature.encode())
        entry = LogEntry(self.log, parent_hash, action, path, content,
            time=time, fingerprint=fingerprint, signature=signature)
        try:
            entry.clean()
        except exceptions.IntegrityError as e:
            sys.stderr.write(str(e)+'\n')
        else:
            entry.validate()
            entry.save()
            # TODO '/tmp/.%s.updated' % self.log.logpath.replace(os.sep, '-')
            utils.touch(self.log.logpath + '.updated')
