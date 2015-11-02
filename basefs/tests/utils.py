import random
import string

from basefs.keys import Key
from basefs.logs import Log


def bootstrap(logpath):
    log = Log(logpath)
    root_key = Key.generate()
    ip = '127.0.0.1'
    log.bootstrap([root_key], [ip])
    return log, root_key


def random_ascii(length=5):
    return ''.join([random.SystemRandom().choice(string.hexdigits) for i in range(0, length)]).lower()

