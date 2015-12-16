import os
import sys
import tempfile
import textwrap
import subprocess

port=18374
serf_udp, serf_tcp, sync = 0, 2, 4
dataset = {}

for filename in sys.argv[1:]:
    with open(filename, 'r') as handler:
        prev = [0, 0, 0, 0, 0, 0]
        result = [0, 0, 0, 0, 0, 0]
        for line in handler:
            # 1449830028.574 udp:18374:0:0
            timestamp, *args = line.split()
            if len(args) != 3:
                raise ValueError
            for arg in args:
                try:
                    pkts, bytes = arg.split(':')[2:]
                except ValueError:
                    raise ValueError(arg)
                if arg.startswith('udp:%i:' % port):
                    protocol = serf_udp
                elif arg.startswith('tcp:%i:' % port):
                    protocol = serf_tcp
                elif arg.startswith('tcp:%i:' % (port+2)):
                    protocol = sync
                else:
                    sys.stderr.write("Unknown protocol '%s'\n" % arg)
                    continue
                if bytes.endswith(('K', 'M')):
                    bytes = int(bytes[:-1])*1000
                elif bytes.endswith('M'):
                    bytes = int(butes[:-1])*1000
                else:
                    bytes = int(bytes)
                pkts = int(pkts)
                result[protocol] = pkts - prev[protocol]
                result[protocol+1] = bytes - prev[protocol+1]
                prev[protocol] = pkts
                prev[protocol+1] = bytes
            try:
                aggregate = dataset[timestamp]
            except KeyError:
                aggregate = [0, 0, 0, 0, 0, 0]
            dataset[timestamp] = [r+a for r,a in zip(result, aggregate)]


with open('/tmp/traffic.csv', 'w') as handler:
    handler.write("Timestamp,Serf UDP pkts,Serf UDP bytes,Serf TCP pkts,Serf TCP bytes,Sync pkts,Sync bytes\n")
    for k, v in dataset.items():
        handler.write(','.join([k] + list(map(str, v)))+'\n')

r = textwrap.dedent("""\
    library("ggthemes")
    library("ggplot2")
    library("tidyr")
    xx = read.csv("/tmp/traffic.csv")
    traffic = gather(xx, "variable", "value", -Timestamp)
    traffic$Bytes = grepl("bytes", traffic$variable)
    traffic$Bytes = factor(ifelse(traffic$Bytes, "Bytes", "Packets"))
    traffic$variable = gsub(".bytes", "", traffic$variable, fixed = T)
    traffic$variable = gsub(".pkts", "", traffic$variable, fixed = T)
    traffic$variable = gsub(".", " ", traffic$variable, fixed = T)
    traffic$Timestamp = traffic$Timestamp - min(traffic$Timestamp)
    ggplot(traffic, aes(x=Timestamp, fill=variable, y=value)) +
        geom_area(position="identity", alpha=0.7) +
        facet_wrap(~Bytes, scales="free_y") +
        theme_bw() +
        scale_fill_tableau()
    ggsave("traffic.png", dpi=600)
    """)
subprocess.Popen("echo '%s' | Rscript -" % r, shell=True)
