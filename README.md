# basefs
Basically Available, Soft state, Eventually consistent File System


**Work in progress**


## Quick start

```bash
# Install
$ pip3 install basefs==1-dev \
    --allow-external basefs \
    --allow-unverified basefs
$ sudo basefs installserf

# Create new key
$ basefs genkey

# Create new log
$ basefs bootstrap mylog -i <ip>

# Mount
$ mkdir ~/mylog
$ basefs mount mylog ~/mylog

# Get the log from another machine
$ basefs get <ip>:<port> mylog
$ mkdir ~/mylog
$ basefs mount mylog ~/mylog

# See all available commands
$ basefs help
Usage: basefs COMMAND [arg...]
       basefs [ --help | -v | --version ]

Basically Available, Soft state, Eventually consistent File System.

Commands:
    mount       Mount an existing filesystem
    handler     Run as Serf handler
    bootstrap   Create a new self-contained filesystem
    genkey      Generate a new EC private key
    keys        List keys and their directories
    grant       Grant key write permission
    revoke      Revoke key write permission
    log         Show a log file using a tree representation
    revert      Revert object to previous state, 'log' command lists all revisions
    blocks      Block state
    members     List cluster members
    get         Get log from peer address
    installserf installserf
    help

Run 'basefs COMMAND --help' for more information on a command
```
