import time
import sys
import os
import zlib
import lzma
import bsdiff4
import json
import math
import matplotlib.pyplot as plt


basepath = sys.argv[1] if len(sys.argv) == 2 else '/etc'

def compress(method):
    ini = time.time()
    results = []
    for path, dirs, files in os.walk(basepath):
        for file in files:
            file = os.path.join(basepath, file)
            if os.path.islink(file):
                packets = 1
            else:
                filename = file.split(os.sep)[-1]
                first_packet = (355 + len(filename))/512
                try:
                    with open(file, 'br') as handler:
                        size = len(method(handler.read()))
                        packets = 1
                        if size > first_packet:
                            packets += math.ceil((size-first_packet)/(512-1-28))
                        if packets > 100:
                            packets = 100
                except (FileNotFoundError, IsADirectoryError):
                    continue
            results.append(packets)
    return results, time.time()-ini

# warm-up
compress(lambda n: '')

results = {
    'raw': compress(lambda n: n),
    'bsdiff4': compress(lambda n: bsdiff4.diff(b'', n)),
    'lzma': compress(lzma.compress),
    'zlib': compress(zlib.compress),
}

plt.hist(results['raw'][0], bins=1000, histtype='step', normed=True, color='y', label='raw', cumulative=True)
plt.hist(results['zlib'][0], bins=1000, histtype='step', normed=True, color='r', label='zlib', cumulative=True)
plt.hist(results['bsdiff4'][0], bins=1000, histtype='step', normed=True, color='g', label='bsdiff4', cumulative=True)
plt.hist(results['lzma'][0], bins=1000, histtype='step', normed=True, color='b', label='lzma', cumulative=True)
plt.title("Gaussian/Uniform Histogram")
plt.xlabel("Value")
plt.ylabel("Probability")
plt.legend()
plt.show()
plt.savefig('/tmp/foo3.png')
plt.clf()


# Example data
plt.barh(1, results['raw'][1], align='center', alpha=0.7, color='y')
plt.barh(2, results['zlib'][1], align='center', alpha=0.7, color='r')
plt.barh(3, results['bsdiff4'][1], align='center', alpha=0.7, color='g')
plt.barh(4, results['lzma'][1], align='center', alpha=0.7, color='b')

plt.yticks((1,2,3,4), ('raw', 'zlib', 'bsdiff4', 'lzma'))
plt.xlabel('Time in seconds')
plt.title('How fast do you want to go today?')

plt.savefig('/tmp/foo.png')

#print(json.dumps(results, indent=4))
