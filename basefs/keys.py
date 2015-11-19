import base64
import hashlib
from collections import defaultdict

import ecdsa


class KeyRing:
    def __init__(self):
        self.keys = {}
    
    def add(self, key, path):
        self.keys[key.fingerprint] = key


class Key(ecdsa.SigningKey):
    _paths = defaultdict(set)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def __hash__(self):
        return hash(self.fingerprint)
    
    def __eq__(self, key):
        return self.fingerprint == key.fingerprint
    
    @property
    def paths(self):
        return self._paths[self.fingerprint]
    
    def add_path(self, path):
        self._paths[self.fingerprint].add(path)
    
    @property
    def fingerprint(self):
        try:
            return self.__cached_fingerprint
        except AttributeError:
            data = self.oneliner()
            keydata = base64.b64decode(data.encode())
            fingerprint = hashlib.md5(keydata).hexdigest()
            self.__cached_fingerprint = ':'.join(a+b for a,b in zip(fingerprint[::2], fingerprint[1::2]))
            return self.__cached_fingerprint
    
    @classmethod
    def load(cls, path):
        with open(path) as handler:
            return cls.from_pem(handler.read())
    
    def oneliner(self):
        return ''.join(self.to_pem().decode().split('\n')[1:-2])
    
    def save(self, path):
        with open(path, 'w') as handler:
            handler.write(self.to_pem().decode())

