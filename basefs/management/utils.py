import os
import sys

from basefs import utils
from basefs.config import get_or_create_config, get_port


def get_cmd_port(args, mount_info, defaults):
    port = mount_info.port if mount_info else None
    name = args.name
    if not port and not name:
        try:
            logs = os.listdir(defaults.logdir)
        except FileNotFoundError:
            sys.stderr.write("Error: logdir '%s' does not exists\n" % defaults.logdir)
            sys.exit(3)
        else:
            if len(logs) == 1:
                name = logs[0]
            else:
                sys.stderr.write("Error: name should be provided when not running inside a mounted basefs filesystem\n")
                sys.exit(3)
    if not port:
        config = get_or_create_config(defaults)
        if name not in config:
            logpath = os.path.join(defaults.logdir, name)
            if os.path.exists(logpath):
                info, __ = utils.get_mountpoint(logpath)
                if info:
                    port = int(info.split(':')[1])
                else:
                    port = get_port(name)+2
            else:
                sys.stderr.write("Error: unknwon logname %s\n" % name)
                sys.exit(2)
        else:
            port = int(config[name].get('port', get_port(name)))+2
    return port


def create_logdir(logpath, default_logpath, force=False):
    logdir = os.path.dirname(logpath)
    if not os.path.exists(logdir):
        if logpath == default_logpath:
            os.mkdir(logdir)
        else:
            sys.stderr.write("Error: %s logdir directory doesn't exist, create it first.\n" % logdir)
            sys.exit(2)
    if os.path.exists(logpath):
        if not force:
            sys.stderr.write("Error: logpath %s already exists and --force argument was not provided\n" % logpath)
            sys.exit(1)
        else:
            os.remove(logpath)
