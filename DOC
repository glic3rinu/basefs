Decentralised Gossip driven
then sync them up in hostile network settings
linked immutable objects synced via a gossip protocol.

Gossip based data replication; reduces network footprint in large networks.


Monotonicity: allways growing
Conflicting writes with the same parent/path (unique:parent/path constrain), consensus model:
    1st Appeal to the people, branch with more valid contributors (incl. aknowladged invalidations)
    2nd Appeal to authority, branch with authors higher in the hierarchy
    3rd solve all conflicts, branch with lower initial hash

Writes from an invalidated key
    Ignore branch tail with invalidated key, not backed by any other fucker.
    * Acknowladge valid contributions on invalidation action



GOOD https://www.serfdom.io/intro/vs-zookeeper.html
http://highscalability.com/blog/2011/11/14/using-gossip-protocols-for-failure-detection-monitoring-mess.html
GOOD Ivy: A Read/Write Peer-to-Peer File System
IgorFs:
http://www.cs.cornell.edu/home/rvr/papers/flowgossip.pdf


limitations imposed by the use of the underlying UDP based gossip service
It means we can send the replicated state for each service registration in one UDP packet. Which is a very, very good thing as it is what allows the underlying gossip work so well and do so simply


Strong consistency guarantees inside the group are not probided, but can be provided in upper layers. Eventual consistent is provided.
