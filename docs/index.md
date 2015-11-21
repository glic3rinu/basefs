overview
========

1. **Write permissions** with decentralized authority
    * PKI-based with eliptic curve cryptoraphy

2. **Available** but not strongly consistent under partition
    * Blockchain inspired consensus mechanism, using *proof-of-authority*

3. Eventual consistency guarantees
    * Monotonic log-based state

4. High tolerance to packet-loss, low-throughput, high-latency and high-churn network conditions
    * Gossip-based data replication over UDP

5. Easy to use
    * File system interface, familiar and consolidated with existing tools

specialized Merkle trees

Properties
==========
a. decentralized state
    Dropbox-like applications: each user with each folder, and shared folders
    SO upgrade on large clusters
    shared configuration for decentralized cloud computing: zookeeper, etcd
    shared in-memory-state for clusters: memcached

b. mutable P2P content
    Mutable P2P file sharing, ok for small files, but incentive mechanissm to avoid free-riders and block sharing swarm may be needed (WRITE magnetlink).
    Live documents: enciclopedia or discographies that self-update when new updates are available

c. monotonicity
    Version control system


Rationel
========

decentralize confine, no controller
use consul or existing solutions: all CP
build new decentralized solution AP
lookup for decentralized authority systems: bitcoin- proof of work a waste of power
git on steroids? single point of conflic: commit blockchain, no Because of receiving fresh updates out-of-sync with commits, no automatic conflict resolution, no built-in permissions
devise a new system for decentralized cluster configuration management



Sync protocol
=============
    LS = 'LS'
    ENTRY_REQ = 'E-REQ'
    PATH_REQ = 'P-REQ'
    ENTRIES = 'ENTRIES'
    CLOSE = 'CLOSE'
    BLOCKS = 'BLOCKS'
    BLOCKS_REC = 'B-REC'
    BLOCK_REQ = 'B-REQ'
    
    B-REC
    /home/user/rata.txt entryhash0 entryhash1
    /etc/samba.conf entryhash2
    LS
    / merklehash0
    
    B-REC
    /usr/rata entryhash0
    LS
    */ entryhash0 entryhash2 entryhash3
    /home merklehash0
    /home merklehash1
    /etc merklehash2
    /usr merklehash3
    
    LS
    */home entryhash4 entryhash5
    /home/pangea merklehas0
    /home/user1 merklehash1
    /home/user2 merklehash2
    */usr entryhash6
    /usr/kakas merklehash5
    
    LS
    */home/user1 entryhash1 entryhash2
    !/home/user1 blockhash19



Receiving: announce and not include on merkletree
Stalled: include entry hash and last received hash on merkle tree
Completed: remove last hash from merkle tree if needed and include entry hash


Update merkle:
    * entry_hash: receiving entry != write
    * entry_hash: receiving all blocks
    * entry_hash + last_block_hash: stalled receiving blocks
    * last_block_hash: if stalled receiving continues or receiving all blocks


For small files it is not really important to give incentives for sharing because the resources that each node has to contribute for becoming part of the network are small. However for large files or very-very large file systemes we can consider to incentive mechanisms:
    a) block-market swarn: write content contains all the blocks hashes of that file, the original content has to be fetched from a bitTorrent-like swarm, much like swaptorrent works (ipfs)
    b) nodes do not contribute all the missing parts when syncing, they can keep track of the behaviour of the other nodes and decide to choke them if appropiate


gossip layer problems: Keep track of bad behaviour and ban bad nodes.

