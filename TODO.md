

basefs bootstrap confine -i 127.0.0.1
basefs mount confine /tmp/ola/ -d
basefs mount confine /tmp/rata/ -b 127.0.0.1:6776 -H rata -d




https://docs.python.org/3/library/configparser.html

make basefs to be able to run multiple times on the same machine for esay testing (solve port issuse)
cluster discovery: /.cluster <ip, port> tuple
WRITE vs WRITE-DELTA


Future work: gossip layer should discard shit
stronger logentry validation to avoid shit (read current branch)

GRANT REVOKE operations over dir/file ?? no more keys file, show as extra attributes: unique key name; lookup for first appearance

remove full path, just relative path (filename/basename): needed for GOTO  (smaller metadata)
mv () implemented like revert() GOTO hash and DELETE origin path
on revoke() WRITE-ACK instead of rewriting everything

autodetect logpath based on current filesystem

basefs revisions path
basefs ls path // in order to see username and permissions 
basefs show revisionnumber
basefs revert revisionnumber // implemented like mv() GOTO hash 
# TODO date in human readable when print_tree() and user to fingerprint match

View.build(partial='/.cluster')

PATH history: WRITE - WRITE - DELETE - MKDIR - DELETE - MKDIR - DELETE - WRITE - WRITE - DELETE


1. Represent keys as separated files and create .keys/by_fingerprint virtual directory with emulated symlinks that delete original file when rm-ed

View should be a proxy of view.entry, should have view.content and when view.save() should diff/override view.entry.content and generate multiple entries if needed, view.entry == view.last/current_entry

how hard would be to write offset [EOF] ? Diff patch 
prevent direct writes to .keys, use view.grant view.revoke
touch implementation: provide stat update functionallity and forget about create(), 
full state sync

use python thread instead of process (FUSE)
Philosophy, design decission: fit existing filesystem tools (find, grep, cat, echo, rm) rather than develop new ones for cluster management
hash is used instead of uuid to avoid forging, and save some bytes on the process

LINK operation
RENAME/MOVE: because its a allways growingg data structure, things can not be moved around, just copied


# LZMA > size, zlib < size binary patch very large: stay with binary patch. decission algorithm:
# Compute binaty patch
# Evaluation graphs and solution:
#   1st patch bsdiff4.diff
#   2nd if slightly larger than 450b > zlib.compress else do nothing 
#   if patch size ~= entire file size: send file ? (optimization)


import hashlib, uuid, lzma, json, operator, marshal, pickle, zlib, random, string
hashfunc = lambda: hashlib.md5(uuid.uuid4().hex.encode()).hexdigest()
random_ascii = lambda length=5: ''.join([random.SystemRandom().choice(string.hexdigits) for i in range(0, length)]).lower()
#a = {hashfunc(): [hashfunc() for i in range(random.randrange(1,10))] for i in range(10000)}
#hashfunc = lambda: int(hashlib.md5(uuid.uuid4().hex.encode()).hexdigest(), 16)
#b = {hashfunc(): [hashfunc() for i in range(random.randrange(1,10))] for i in range(10000)}

hashfunc = lambda: hashlib.md5(uuid.uuid4().hex.encode()).hexdigest()
a = '\n'.join(['%s %s' % (random_ascii(random.randint(5, 100)), hashfunc()) for i in range(25)])
hashfunc = lambda: int(hashlib.md5(uuid.uuid4().hex.encode()).hexdigest(), 16)
b = '\n'.join(['%s %s' % (random_ascii(random.randint(5, 100)), hashfunc()) for i in range(25)])

results = {
    'str_json': len(json.dumps(a).replace(' ', '')),
    'int_json': len(json.dumps(b).replace(' ', '')),
    'str_marshal': len(marshal.dumps(a)),
    'str_pickle': len(pickle.dumps(a)),
    'int_marshal': len(marshal.dumps(b)),
    'int_pickle': len(pickle.dumps(b)),
    
    'str_zlib': len(zlib.compress(a.encode())),
    'int_zlib': len(zlib.compress(b.encode())),
    'str_json_zlib': len(zlib.compress(json.dumps(a).replace(' ', '').encode())),
    'int_json_zlib': len(zlib.compress(json.dumps(b).replace(' ', '').encode())),
    'str_marshal_zlib': len(zlib.compress(marshal.dumps(a))),
    'str_pickle_zlib': len(zlib.compress(pickle.dumps(a))),
    'int_marshal_zlib': len(zlib.compress(marshal.dumps(b))),
    'int_pickle_zlib': len(zlib.compress(pickle.dumps(b))),
    
    'str_lzma': len(lzma.compress(a.encode())),
    'int_lzma': len(lzma.compress(b.encode())),
    'str_json_lzma': len(lzma.compress(json.dumps(a).replace(' ', '').encode())),
    'int_json_lzma': len(lzma.compress(json.dumps(b).replace(' ', '').encode())),
    'str_marshal_lzma': len(lzma.compress(marshal.dumps(a))),
    'str_pickle_lzma': len(lzma.compress(pickle.dumps(a))),
    'int_marshal_lzma': len(lzma.compress(marshal.dumps(b))),
    'int_pickle_lzma': len(lzma.compress(pickle.dumps(b))),
    
}
for k, v in sorted(results.items(), key=operator.itemgetter(1)):
    print(k + (' '*(20-len(k))) + str(v) +'b' + ' '*(14-len(str(v))) +str(float(v)/1000) + 'kb')
int_marshal_lzma    1054408b       1054.408kb
str_json_lzma       1069448b       1069.448kb
str_marshal_lzma    1072200b       1072.2kb
int_pickle_lzma     1081656b       1081.656kb
int_json_lzma       1087072b       1087.072kb
int_pickle_zlib     1102813b       1102.813kb
int_marshal_zlib    1105033b       1105.033kb
str_pickle_lzma     1147068b       1147.068kb
int_json_zlib       1151364b       1151.364kb
str_marshal_zlib    1176202b       1176.202kb
int_pickle          1182889b       1182.889kb
str_json_zlib       1188560b       1188.56kb
str_pickle_zlib     1413080b       1413.08kb
int_marshal         1423334b       1423.334kb
str_marshal         2085514b       2085.514kb
str_json            2115381b       2115.381kb
int_json            2409579b       2409.579kb
str_pickle          2592632b       2592.632kb

###############
import bsdiff4
def random_ascii(length=5):
    return ''.join([random.SystemRandom().choice(string.hexdigits) for i in range(0, length)]).lower()
a = bytes(100000 * b'a')
b[100:106] = b' diff '
p = bsdiff4.diff(a, bytes(b))
len(p)
len(zlib.compress(p))
len(lzma.compress(p))

a = b''
b = random_ascii(100000).encode()
p = bsdiff4.diff(a, b)
len(p)
len(zlib.compress(p))
len(zlib.compress(b))
len(lzma.compress(b))



a = random_ascii(10000).encode()
c = random_ascii(100).encode()
b = a + c 
p = bsdiff4.diff(a, b)
len(p)
len(zlib.compress(p))
len(zlib.compress(c))

a = random_ascii(100000).encode()
c = random_ascii(100000).encode()
b = a + c 
p = bsdiff4.diff(a, b)
len(p)
len(zlib.compress(p))
len(zlib.compress(c))
len(lzma.compress(p))
len(lzma.compress(c))




# Hash truncate sha256
import time, string, random
def random_ascii(length=5):
    return ''.join([random.SystemRandom().choice(string.hexdigits) for i in range(0, length)]).lower()

now = time.time()
a = [hashlib.sha256(random_ascii(512).encode()) for i in range(10000)]
print('sha ' + str(time.time()-now))
now = time.time()
a = [hashlib.md5(random_ascii(512).encode()) for i in range(10000)]
print('md5 '+str(time.time()-now))

# MD5 is broken use hashlib.sha256(random_ascii(512).encode()).hexdigest()[:32]


# Calculate average and so
import zlib
g = 0
l = 0
for line in open('/tmp/merda', 'r').readlines():
 with open(line.strip(), 'rb') as handler:
  size = len(zlib.compress(handler.read()))
  if size > 400:
    g += 1
    print(line.strip(), size)
  else:
    l += 1


print(l, g)

