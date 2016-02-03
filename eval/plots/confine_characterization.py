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
C = nx.Graph()

basefspath = os.getenv('BASEFSPATH')

latencies = []
nhops = []
origins = set()
c_origins = set()


trace_path = os.path.join(basefspath, 'eval/datasets/confine-traceroute')
plot_path = os.path.join(basefspath, 'eval/plots')


with open(os.path.join(trace_path, '0', 'traceroute'), 'r') as handler:
    mainip = handler.readline().split()[0]

print("Main IP: %s" % mainip)

ip_to_name = {}

for node in os.listdir(trace_path):
    filename = os.path.join(trace_path, str(node), 'traceroute')
    with open(filename, 'r') as handler:
        ip = handler.readline().split()[0]
        ip_to_name[ip] = str(node)

cluster = ['1', '10', '30', '11', '29', '17', '16', '8', '9', '14', '0']

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
            ip_to_name[origin] = filename.split('/')[-2]
            latencies.append(float(latency))
            hops = line.split()[3:]
            origins.add(ip_to_name[origin])
            origins.add(ip_to_name[target])
            nhops.append(len(hops))
            prev_origin = origin
            for hop in hops:
                if hop in ('deploy', 'experiment'):
                    continue
                G.add_edge(ip_to_name.get(origin, origin), ip_to_name.get(hop, hop), weight=0.2, color='blue')
                origin = hop
            origin = prev_origin
            if ip_to_name[origin] not in cluster and ip_to_name[target] not in cluster:
                c_origins.add(ip_to_name[origin])
                c_origins.add(ip_to_name[target])
                for hop in hops:
                    if hop in ('deploy', 'experiment'):
                        continue
                    C.add_edge(ip_to_name.get(origin, origin), ip_to_name.get(hop, hop), weight=0.2, color='blue')
                    origin = hop

origins.remove('0')

print("Good nodes: %s" % good_nodes)

labels = {}
for node in G.nodes():
    if '.' not in node:
        labels[node] = node

pos = nx.graphviz_layout(G, prog='neato')

# nodes
nx.draw_networkx_nodes(G, pos, node_size=10, node_color='y', with_labels=False)
nx.draw_networkx_nodes(G, pos, nodelist=['0'], node_size=60, node_color='r')
nx.draw_networkx_nodes(G, pos, nodelist=origins, node_size=30, node_color='b')

# edges
nx.draw_networkx_edges(G, pos)

# labels
nx.draw_networkx_labels(G, pos, labels, font_size=14)


plt.axis('off')
weighted_graph_neato_path = os.path.join(plot_path, "weighted_graph_neato.png")
plt.savefig(weighted_graph_neato_path, dpi=300) # save as png
print("eog " + weighted_graph_neato_path)
plt.clf()

#c_origins.remove('0')
c_labels = {}
for node in C.nodes():
    if '.' not in node:
        c_labels[node] = node

c_pos = nx.graphviz_layout(C, prog='neato')
nx.draw_networkx_nodes(C, c_pos, node_size=10, node_color='y', with_labels=False)
#nx.draw_networkx_nodes(C, c_pos, nodelist=['0'], node_size=60, node_color='r')
nx.draw_networkx_nodes(C, c_pos, nodelist=c_origins, node_size=30, node_color='b')
nx.draw_networkx_edges(C, c_pos)
nx.draw_networkx_labels(C, c_pos, c_labels, font_size=14)

plt.axis('off')
weighted_graph_neato_cluster_path = os.path.join(plot_path, "weighted_graph_neato_cluster.png")
plt.savefig(weighted_graph_neato_cluster_path, dpi=300) # save as png
print("eog " + weighted_graph_neato_cluster_path)
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
