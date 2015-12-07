Decentralized state for cluster management

Without central servers

decentralized coordination

community cloud: under the assumption than its an heterogenous pool of machines unreliable, underutilized resources...

Coordination Layer. To achieve coordination, the nodes need to be deployed
as isolated virtual machines, forming a fully distributed P2P network that can
provide support for distributed identity, trust, and transactions.


Introduction
============

One of the steps towards building a successful distributed system is establishing effective configuration management. It is a complex engineering process which is responsible for planning, identifying, tracking and verifying changes in the software and its configuration as well as maintaining configuration integrity throughout the life cycle of the system. [1]

Some successfull tools exist to aid in this process, Chef and Pupet only for naming two. The common theme is having static configuration, or recepies, that converge every few minutes. This approach works great with static configuration but fails to provide an ideal solution for a more dynamic state, where a near real-time convergense is desirable. Because of the need of faster provisioning (i.e. elasticity in cloud environments) systems like Zookeeper, etcd or Consul have emerged that solve this specific problem. They are distributed K/V stores holding the global state of the system. Perhaps a distintion can be made between the more static configuration management tasks solved by tools like Chef or Pupet and the more dynamic cluster management commonly solved by K/V stores like Zookeeper, etcd or Consul.

The mentioned cluster management solutions have a very similar architecture, they have server nodes that require a quorum of nodes to operate (usually a simple majority). They chose consistency over availability under the face of a network partition. [2] This design deciession is based on the assumption that these systems are deployed on a data center environment, where machines are homogeneous with predictable performance, the network is fast, churn is low and they have a dedicated professional operations team, part of a single administrative domain. But this assumptions are not allways true, think about internet of things (IoT), community cloud computing or grid computing.

Internet of things (IoT) is a growing trend of networking every single electronic device, sensors and actuators. Here we have lots of low power mobile devices that can not be connected all the time because of energy or coverage constrains. On the other hand, community cloud computing is an emerging model where infraestructure is built using a collaborative effort. It is often the result of each user providing its sparce resources to a common pool. As we can imagine the set of constrains are different from those in a traditional datacenter. in terms of network characteristics (partitions, latency, throughput) administration and camapcity to handle deployment complexities.

Identity in the Community Cloud has to arise naturally from
the structure of the network, based on the relation of nodes to each other, so that it
can scale and expand without centralised control.
Networking: At this level, nodes should be interconnected to form a P2P
network. Engineered to provide high resilience while avoiding single points of
control and failure, which would make decentralised super-peer based control
mechanisms insufficient. Newer P2P designs [21] offer sufficient guarantees of
distribution, immunity to super-peer failure, and resistance to enforced control.

http://link.springer.com/chapter/10.1007/978-3-642-10665-1_43

networked personal computers to provide the facilities of data centres,

Grid Computing,


On these environment machines tend to be heterogenous, networks are often build and operated by the same community with consumer-grade wireless equipment. Because of interference, hardware failure or operational human errors network partitions are not rare. 

The main contribution of this thesis is to provide a new approach to solve cluster management problems on a decenetralized more networked constrain environments. We present an eventual consistent distributed file system specifically design for cluster and configuration management.



Background
==========
Zookeeper, etch and Consul are distributed key value stores for shared configuration and service discovery, but they all present some limitations in the context of community cloud computing or IoT.

1. Scalability limits
In Zookeeper et al, distributed strong consistency is achived using Paxos, or Paxos-like, consensus algorithm (raft), which needs the majority of the nodes to agree on every decission. Even though consensus gets progressively slower as more machines are added, these systems scale resonabily well in terms of load just by adding more servers to the consensus pool. However, scalability means more than size. The challange lies in geographical and administrative scalability; the maximum distance between nodes and number of administrative domains.

Geographical scalability:
    Because ZooKeeper et al chose to have strong consistency, constant comunication to achieve consensus on every decission is needed. Constant communication makes the system sensitive to latency and moving the servers appart will lower its performance. Consul is the only solution that provides native support for inter-datacenter deployments, it provides mitigations for the effects of high latency: Forwarding request to the correct DC where the leader resides, caching. However these mitigations don't solve the problem... 

Administrative scalability:
    Permissions are provided from the interface prespective. The system is not secure to be operated by multiple administrative entities that don't fully trust each other. centralized authority

2. Availability under network partition

The CAP theorem is commonly used for reassoning about the tradeoffs made on the design of a distributed system. The achrnonym stands for:
    Consistency (strong): All nodes see the same data at the same time.
    Availability: node failures do not prevent survivors from continuing
    Partition tolerance: the system continues to operate despite message loss due to network failure

The theorem states that a distributed system, under a network partition, has to choose between being available or being consistent. In our case all the current solutions err on the side of consistency, these solutions are commonly called CP (Consistent but not available under partition). The main implication is that in case of partition nodes under a miniority partition will not be able to perform writes.

    It is important to notice that consistency on the CAP theorem refers to *strong consistency*, the definition can be relaxed and allow availability and some kind of consistency less than "all nodes see the same data at the same time". For example eventual consistency; after some undefined amount of time all replicas will converge on the same value.

CP solutions work well within environments with stable network conditions and relatively low churn, conditions where partitions are rare. However, if you move to a bad network conditions, high churn  and strong consistency is not absolutelly required then you may be better off with a system that falls into the AP side of the spectrum (available but not consistent under partition). This system will allow continous operation, even for complitely offline nodes, and they will converge when they go back online. The system should focus on reducing this divergence time as much as possible, limiting the number of points of conflict and provide fast convergence communication between nodes.


3. Deployment complexity

The complexity of the solution is something to take into account when the operators are inter-administrative domains and have low level of expertise and time because 
They run on dedicated servers, they need to be well connected, and partitions kill availability. System should be secured, bizzantine attacks.
P2P system are easy to deploy, look at bittorrent which has been deployed on a massive scale.

usage complexity
Easy to use
    * File system interface, familiar and consolidated with existing tools, fs hierarchy desirable way of organizing data objects



Related technologies
====================
Because we don't want to reinvent the wheel we analyze some successfull technologies on distributed systemes that could be used as inspiration or part of our solution.

NoSQL

The first thing that comes to mind when thinking about an AP distributed K/V store is to look at the NoSQL world, where databases like cassandra or riak have been around for a while. The problem 

IPFS

BitCoin

GIT

Design
======

Here we have ideas of successfull distributed systems like bitcoin, ipfs, bittorrent and git.

log
===

A log is composed by three types of objects:
    log entry
    block list
    block

We call "log" to the data-structure used for storing all the system shared state. Because we need the state to be eventually consistent the log has to be monotonic, information can not be deleted, just added. Also because we can not trust what other basefs nodes say it needs to be tamper resistant. BaseFS uses a Merkle DAG, a direct acyclic graph where links between objects are cryptograhic hashes of the targets, probiding many useful properties, including:

Content adressing: all content is uniquely identified by its sha224 hash checksum.
Tamper resistance: all content is verified with its hash.
Deduplication: all objects that hold the exact same content are equal, and only stored once.

The BaseFS log entry format is as follows:

timestamp: a UNIX timestamp that represents the time at which the log entry was created. BaseFS does not provide any mechanism to validate this timestamp with a global clock, this field is purely informative used for example by te *ls* command.

action: we have devised some actions needed for enabling all the requirements commonly 
    mkdir: make directory
    create: create a new file
    update: update a file content
    delete: deletes an entry
    revert: reverts a path to some previous state
    grant: enables write permissions to specific key
    revoke: disables write permissions for an specific key
    ack: marks a log entry valid, needed for maintaining state after key revokation
    link: a hard link between two entries
    slink: a symbolic link to a dir or file
    mode: give executable permissions to a file

name: determines the name of the directory, file, link or key. Like UNIX file names, BaseFS name size is limited to 256 characters. Paths are constructed using these names.

content: depending on the action, the log entry content may contain:
    create: first block hash
    grant: EC public key
    slink: target path
    link and revert: target entry hash
    mode: mode value

file size: size of the file, this is a performance optimization because computing the whole file size every time an ls is performed is expensive. 6 bytes are assigned to this field, limiting the mazimum file size to 2 PiB.

key fingerprint: The public key fingerprint used to sign the log entry.

Signature: the Elliptic curve sha224 signature of this entry. Elliptic curve cryptography is used for the smaller size of the keys compared to equivalent RSA security level.




In order for the state to be eventually consistent we need mono

    merkle dag (hash integrity) merkle dag and monotonicity for eventual consistency

    actions
    tree

    entries vs blocks
    why not git?

view
====
    conflicts


filesystem, fuse
    

State replication
=================

BaseFS uses two different protocols for communicating updates to other nodes: a) gossip protocol and b) synchronization protocol

Gossip protocol
===============

A gossip protocol is a style of computer-to-computer communication protocol inspired by the form of gossip seen in social networks. 


Synchronization Protocol
========================

while gossip produces the initial spread of information, anti-entropy is run infrequently to make sure all update are spread with probability 1.


how it works?

 for real-time events and small files and b) synchronization protocol, for recovering after partition or retriving updates af


    messages
    etc characterization
    size matters 512b problem and n messages: ec cryptography, use bytes instead of text

sync protocol (merkle)


File System
===========

The filesystem is implemented using a Python port of FUSE. FUSE is a blabla, very easy, bla bla


.1 Watchers
========
because pulling is shit.
FUSE does not implement support for inotify, so we decided to provide support for subscribing handlers to filesystem events that we call watchers. So code can be executed every time a particular interesting update occur.


handler, watcher, etc
    implement watchers to allow nodes to receive timely notifications of changes without continous polling




decentralized servide discovery with DNS

all components
    * .basefs/state cluster configuration and state

Using basefs










4. High tolerance to packet-loss, low-throughput, high-latency and high-churn network conditions
    * Gossip-based data replication over UDP


centralized authority

1. **Write permissions** with decentralized authority
    * PKI-based with eliptic curve cryptoraphy

2. **Available** but not strongly consistent under partition
    * BitCoin blockchain inspired consensus mechanism, using *proof-of-authority*





Our main contribution in this paper is a 

[1] http://sysgears.com/articles/managing-configuration-of-distributed-system-with-apache-zookeeper/
[2] CAP theorem


IoT  and new ways of distributed computing. 
Provide unmatching scale untrusted shit: bitcoin and all


single administrative domain with unlimited access to all the system. Don't scale in administrative domains

Our main contribution in this paper is a different way of doing distributed configuration management, we present a new approach its only a part of the whole stack of tools and protocols needed for succesfull production deployments.





low-latency in cross-datacenter operations



*KEy point* decentralized authority: AP other solutions only offer single authority strategy, permission system has to be build on top of the merkle dag (data) oon top of ipfs or cassandra/riak. Because our solutions needs to be modeled on top of these storage/block replication solutions we decide to roll our own because of flexibility on designing the underlying infraestructure: rt communicaion with gossip layer, block replication protocol optimized for small files (configuration) and fast lookup time. otherwise will be very opinionated according on what those system provides by default.

Define the problem:
    Which problem do we have?
    Why decentralized cloud computing?
    confine? or more general view?

Why do we need another tool?
What is 

There are lots of consolidated solutions for cluseter management, but all of them are CP. Which is great and all but it will be hard to build a fully decentralized cluster management system. 
Decentralized cluster configuration with untrusted participants and decentralized authority:
Don't solve bizantine problems, and have all nodes share the same secret: centralized authority.






CONSUL, etcd, zookeeper: CP
NoSQL: not scalable in number of nodes? think about distributed key value store systems AP. Permissions semantics for decentralized authority not implemented
IPFS: inefficient mutability propagation and write permissions on the same file? convergence time much greater than basefs
    # TODO how ipfs implements mutability? maybe test it and see how it behaves under cluster config conditions
    * worst problem is how implement write permissions? ipfs seems to only allow writes by a single private key, revokation?

confine on steroids: no central server. higher scalability


flexibility of rolling our own solution and not being tide to specific implementation that tries to solve specific or generic problems on other domains.



overview
========



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



Related work / state of the art
===============================

IPFS
syncthing
btsync
cassandra/mongo/couchdb... nosql databases
consul/etcd


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



Biased getPeer(randomize algorithm) : network proximity, published new content

gossip initial spread of information, anti-entropy is run infrequently to make sure all update are spread with probability 1.






Background
==========

From CAP prespective
===




Evaluation (maybe merge with basefs design (support the design decissions with evidence))
=========

IPFS vs BaseFS

gossip layer saturation limit
etc characterization
    bsdiff (designed for executables) ram hungry: bsdiff is quite memory-hungry. It requires max(17*n,9*n+m)+O(1) bytes of memory, where n is the size of the old file and m is the size of the new file. bspatch requires n+m+O(1) bytes.

convergence time of sync protocol
convergence time gosssip layer
Fs memory and time vs ext4 or other filesystems: iotests (networked vs single node tests)
NAT resistance

The future
===========

diff of large files, don't put them in memory: fs mount option?

enabler for decentralizate cloud platforms

gossip layer problems: Keep track of bad behaviour and ban bad nodes.

For small files it is not really important to give incentives for sharing because the resources that each node has to contribute for becoming part of the network are small. However for large files or very-very large file systemes we can consider to incentive mechanisms:
    a) block-market swarn: write content contains all the blocks hashes of that file, the original content has to be fetched from a bitTorrent-like swarm, much like swaptorrent works (ipfs)
    b) nodes do not contribute all the missing parts when syncing, they can keep track of the behaviour of the other nodes and decide to choke them if appropiate




conclusions
===========

we presented a system with properties that enables more than decentralize configuration.
