python3 -c 'import zlib, sys, string, random, time, base64, bsdiff4, lzma, os, hashlib
filename = "ShiftOmnibusEditionUnabridgedPart1.mp3"
size = os.stat(filename).st_size
with open(filename, "rb") as handler:
    half = int(int(size)/2)
    handler.seek(half)
    test = handler.read(min(512*10, half/2))
    test = handler.read()
    ini = time.time()
    print(len(test), time.time() - ini)
    ini = time.time()
    print(len(bsdiff4.diff(b"", test)), time.time()- ini)
    ini = time.time()
    print(len(zlib.compress(test)), time.time()-ini)
    ini = time.time()
    print(len(lzma.compress(test)), time.time()-ini )
    

'


python3 -c 'import zlib, sys, string, random, time, base64, bsdiff4, lzma, os, hashlib
random_ascii = lambda length: "".join([random.SystemRandom().choice(string.hexdigits) for i in range(0, length)]).lower()
sizes = list([ random.randint(100, 1000) for i in range(0, 5000) ])

ini = time.time()
ant = b""
with open("rata2", "+wb") as rata:
 for size in sizes:
  current = random_ascii(size).encode()
  line = base64.b64encode(bsdiff4.diff(ant, current))
  rata.write(line + b"\n")
  ant = current

print("bsdiff-write", time.time() - ini)

ini = time.time()
ant = b""
with open("rata2", "rb") as rata:
    for ix, line in enumerate(rata.readlines()):
        ant = bsdiff4.patch(ant, base64.b64decode(line.strip()))

print("bsdiff-read", time.time() - ini)

ini = time.time()
with open("rata", "wb") as rata:
 for size in sizes:
  rata.write(base64.b64encode(zlib.compress(random_ascii(size).encode())) + b"\n")

print("compress-write", time.time() - ini)

ini = time.time()
with open("rata", "rb") as rata:
    for line in rata.readlines():
        line = zlib.decompress(base64.b64decode(line.strip()))

print("compress-read", time.time() - ini)

ini = time.time()
with open("rata", "rb") as rata:
    for line in rata.readlines():
        line = base64.b64decode(line.strip())

print("base64-read", time.time() - ini)


ini = time.time()
with open("rata", "rb") as rata:
    for line in rata.readlines():
        line = hashlib.sha256(base64.b64decode(line.strip()))

print("sha256-read", time.time() - ini)

'


