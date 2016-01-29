import sys
import textwrap
import subprocess


entryhashes = {}
filenames = []
for filename in sys.argv[1:]:
    if 'node-0' in filename:
        with open(filename, 'r') as handler:
            for line in handler:
                timestamp, entryhash = line.split()
                entryhashes[entryhash] = [timestamp]
    else:
        filenames.append(filename)


for filename in filenames:
    with open(filename, 'r') as handler:
        for line in handler:
            timestamp, entryhash = line.split()
            try:
                entryhashes[entryhash].append(timestamp)
            except KeyError:
                sys.stderr.write("Key error %s\n" % entryhash)


with open('/tmp/convergence.csv', 'w') as handler:
    handler.write('Entryhash,Time\n')
    for entryhash, timestamps in entryhashes.items():
        dataset = [0]
        ini = float(timestamps[0])
        handler.write('%s,%s' % (entryhash, 0) + '\n')
        for timestamp in sorted(timestamps[1:]):
            handler.write('%s,%s' % (entryhash, float(timestamp)-ini) + '\n')


r = textwrap.dedent("""\
    xx = read.csv("/tmp/convergence.csv")
    library(ggplot2)
    library(ggthemes)
    ggplot(xx, aes(x=Time, color=Entryhash)) +
        xlab("Time in Seconds") + ylab("Convergence") + scale_y_continuous(breaks=seq(0, 1, 0.1)) +
        stat_ecdf() + theme_bw() + scale_color_tableau() + guides(color=F) +
        coord_cartesian(xlim=c(-1, max(xx$Time)+2)) + scale_x_continuous(breaks=pretty(xx$Time, 10)) +
    ggsave("convergence.png", dpi=600)
    """)
subprocess.Popen("echo '%s' | Rscript -" % r, shell=True)

