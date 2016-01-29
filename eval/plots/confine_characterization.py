#!/usr/bin/python

# pip install -Iv https://pypi.python.org/packages/source/p/pyparsing/pyparsing-1.5.7.tar.gz#md5=9be0fcdcc595199c646ab317c1d9a709
# python traceroure.py results/2016.01.21-18\:29\:13/*/traceroute

import os
import copy
import sys
import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from scipy import stats

G = nx.Graph()

basefspath = os.getenv('BASEFSPATH')

latencies = []
nhops = []
origins = set()

trace_path = os.path.join(basefspath, 'eval/datasets/confine-traceroute')
plot_path = os.path.join(basefspath, 'eval/plots')


with open(os.path.join(trace_path, '0', 'traceroute'), 'r') as handler:
    mainip = handler.readline().split()[0]

print("Main IP: %s" % mainip)

good_nodes = 0
for node in os.listdir(trace_path):
    filename = os.path.join(trace_path, str(node), 'traceroute')
    with open(filename, 'r') as handler:
        good = False
        for line in handler:
            if mainip == line.split()[1]:
                good = True
        if not good:
            continue
        good_nodes += 1
        handler.seek(0)
        for line in handler:
            origin, target, latency = line.split()[:3]
            latencies.append(float(latency))
            hops = line.split()[3:]
            origins.add(origin)
            origins.add(target)
            nhops.append(len(hops))
            for hop in hops:
                if hop in ('deploy', 'experiment'):
                    continue
                G.add_edge(origin, hop, weight=0.2, color='blue')
                origin = hop

origins.remove(mainip)

print("Good nodes: %s" % good_nodes)


pos = nx.graphviz_layout(G, prog='neato')

# nodes
nx.draw_networkx_nodes(G, pos, node_size=10, node_color='y')
nx.draw_networkx_nodes(G, pos, nodelist=[mainip], node_size=60, node_color='r')
nx.draw_networkx_nodes(G, pos, nodelist=origins, node_size=30,node_color='b')

# edges
nx.draw_networkx_edges(G, pos)

# labels
nx.draw_networkx_labels(G, pos, font_size=5, font_family='sans-serif')

plt.axis('off')
weighted_graph_neato_path = os.path.join(plot_path, "weighted_graph_neato.png")
plt.savefig(weighted_graph_neato_path, dpi=300) # save as png
print("eog " + weighted_graph_neato_path)

plt.clf()
latencies = sorted(latencies)
density = stats.kde.gaussian_kde(latencies)
plt.plot(latencies, density(latencies))
plt.xlabel('Time in ms')
plt.ylabel('Density')
plt.title('Latency Density')
#plt.hist(latencies, bins=30) #np.logspace(0.01, 0.5, 50))
#plt.gca().set_xscale("log")
latencies_path = os.path.join(plot_path, "latencies.png")
plt.savefig(latencies_path, dpi=300)
print("eog " + latencies_path)

plt.clf()
plt.hist(nhops, bins=15)
plt.title('Hops per link')
plt.ylabel('Number of links')
plt.xlabel('Number of hops')
hops_path = os.path.join(plot_path, "hops.png")
plt.savefig(hops_path, dpi=300)
print("eog " + hops_path)
