# basefs
Basically Available, Soft state, Eventually Consistent File System

* [paper](https://github.com/glic3rinu/basefs/raw/master/paper/basefs.pdf)
* [presentation](http://glic3rinu.github.io/basefs/presentation/)


BaseFS is a peer-to-peer distributed filesystem for cloud configuration, designed to operate under the network conditions
and administrative requirements commonly found on Wireless Community Networks. Nodes do not need to trust each
other, the core data-structure is an append-only specialized Merkle tree with monotonic and cryptographic properties
that allows for efficient and secure verification of data sent by untrusted nodes. Decentralized write permission is achieve
using a hierarchy-based public key infrastructure built into the Merkle tree, allowing for automatic resolution of write
conflicts based on proof-of-authority. Finally, a gossip layer provides scalable change dissemination and group membership,
with time and load constant relative to group size. With no single point-of-failure, BaseFS can provide levels of availability and scalability never seen before on a cloud configuration tool

## Quick start

1. Installation
```bash
$ sudo pip3 install basefs
```

2. Bootstrap and mount
```bash
# Create new key
$ basefs genkey

# Createw new filesystem
$ basefs bootstrap myfs -i <ip>

# Mount
$ mkdir ~/myfs
$ basefs mount myfs ~/myfs
```

3. Distribute
```bash
# Get the log from another machine
$ basefs get myfs <ip>
$ mkdir ~/myfs
$ basefs mount myfs ~/myfs
```

4. See all possibilities
```bash
$ basefs help
Usage: basefs COMMAND [arg...]
       basefs [ --help | -v | --version ]

Basically Available, Soft state, Eventually consistent File System.

Commands:
    mount       Mount an existing filesystem
    run         Run an existing filesystem without mounting it (testing)
    bootstrap   Create a new self-contained filesystem
    genkey      Generate a new EC private key
    keys        List keys and their directories
    grant       Grant key write permission
    revoke      Revoke key write permission
    list        List all available logs
    show        Show a log file using a tree representation
    revert      Revert object to previous state, 'log' command lists all revisions
    blocks      Block state
    members     List cluster members
    serf        Serf RPC Command proxy
    get         Get log from peer address
    installserf Download and install Serf
    resources   Display BaseFS resource consumption in real-time
    help

Run 'basefs COMMAND --help' for more information on a command
```
