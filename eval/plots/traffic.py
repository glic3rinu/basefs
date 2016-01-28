# python3 traffic.py logs/*-resources

import os
import re
import statistics
import sys
import tempfile
import textwrap
import subprocess

port = 18374
serf_udp, serf_tcp, sync = 0, 2, 4
dataset = {}
total_bytes = {}


for filename in sys.argv[1:]:
    with open(filename, 'r') as handler:
        prev = [0, 0, 0, 0, 0, 0]
        result = [0, 0, 0, 0, 0, 0]
        for line in handler:
            # name:user:system:threads:vctxtswitches:nctxtswitches:swap:size:resident:shared:text:data:pkts:bytes[:pkts:bytes]
            # 1450808755.89306 basefs:0:0:43:0:7:325:87:0:119146:4890:1165:726:97825 serf:0:0:0:0:4:0:7:114:40:0:3160:1404:986:989:1041
            # 1449830028.574 udp:18374:0:0
            timestamp, basefs, serf = line.split()
            data = (
                (serf_udp, serf.split(':')[-4:-2]),
                (serf_tcp, serf.split(':')[-2:]),
                (sync, basefs.split(':')[-2:]),
            )
            
            for protocol, values in data:
                pkts, bytes = map(int, values)
                result[protocol] = pkts - prev[protocol]
                result[protocol+1] = bytes - prev[protocol+1]
                prev[protocol] = pkts
                prev[protocol+1] = bytes
            try:
                aggregate = dataset[timestamp]
            except KeyError:
                aggregate = [0, 0, 0, 0, 0, 0]
            dataset[timestamp] = [r+a for r,a in zip(result, aggregate)]
    # Last traffic value is the total one
    node = re.findall(r'.*-([0-9]+)-.*', filename)[0]
    try:
        total_bytes[node].append((prev[1], prev[3], prev[5]))
    except KeyError:
        total_bytes[node] = [(prev[1], prev[3], prev[5])]


with open('datasets/traffic.csv', 'w') as handler:
    handler.write("Timestamp,Serf UDP pkts,Serf UDP bytes,Serf TCP pkts,Serf TCP bytes,Sync pkts,Sync bytes\n")
    for k, v in dataset.items():
        handler.write(','.join([k] + list(map(str, v)))+'\n')


with open('datasets/traffic-distribution.csv', 'w') as handler:
    handler.write("Node,Serf UDP bytes,Serf TCP bytes,Sync bytes\n")
    for k in sorted(total_bytes.keys()):
        v = [0, 0, 0]
        for ix in (0, 1, 2):
            v[ix] = map(statistics.mean, [b[ix] for b in total_bytes[k]])
        handler.write(','.join([k] + list(map(str, v)))+'\n')


r = textwrap.dedent("""\
    library("ggthemes")
    library("ggplot2")
    library("tidyr")
    library("reshape2")
    xx = read.csv("datasets/traffic.csv")
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
    
    xx = read.csv("datasets/traffic-distribution.csv")
    traffic<- melt(xx, id.var="Node")
    ggplot(traffic, aes(x = Node, y = value, fill = variable)) + 
      geom_bar(stat = "identity")
    ggsave("traffic-distribution.png", dpi=600)
    """)
subprocess.Popen("echo '%s' | Rscript -" % r, shell=True)
