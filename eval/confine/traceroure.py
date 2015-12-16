import sys

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

G = nx.Graph()

latencies = []
nhops = []
origins = set()
for filename in sys.argv[1:]:
    with open(filename, 'r') as handler:
        good = False
        for line in handler:
            if '10.228.207.204' == line.split()[1]:
                good = True
        if not good:
            continue
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


pos = nx.graphviz_layout(G, scale=3, prog='circo')

origins.remove('10.228.207.204')
# nodes
nx.draw_networkx_nodes(G, pos, node_size=10, node_color='y')
nx.draw_networkx_nodes(G, pos, nodelist=['10.228.207.204'], node_size=60, node_color='r')
nx.draw_networkx_nodes(G, pos, nodelist=origins, node_size=30,node_color='b')


# edges
nx.draw_networkx_edges(G, pos)

# labels
nx.draw_networkx_labels(G, pos, font_size=5, font_family='sans-serif')

plt.axis('off')
plt.savefig("weighted_graph.png", dpi=300) # save as png

plt.clf()
from scipy import stats
latencies = sorted(latencies)
density = stats.kde.gaussian_kde(latencies)
plt.plot(latencies, density(latencies))
plt.xlabel('Time in ms')
plt.ylabel('Density')
plt.title('Latency Density')
#plt.hist(latencies, bins=30) #np.logspace(0.01, 0.5, 50))
#plt.gca().set_xscale("log")
plt.savefig('latencies.png', dpi=300)

plt.clf()
plt.hist(nhops, bins=15)
plt.title('Hops per link')
plt.ylabel('Number of links')
plt.xlabel('Number of hops')
plt.savefig('hops.png', dpi=300)
