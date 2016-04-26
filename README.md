# basefs
Basically Available, Soft state, Eventually Consistent File System

* [paper](https://github.com/glic3rinu/basefs/raw/master/paper/basefs.pdf)
* [presentation](http://glic3rinu.github.io/basefs/presentation/)


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
$ basefs get myfs <ip>:<port>
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
