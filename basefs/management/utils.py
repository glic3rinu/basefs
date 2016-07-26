import os
import re
import sys

from basefs import utils
from basefs.config import get_or_create_config, get_port


def get_context(arg, defaults):
    def get_from_logpath(filesystems, logpath):
        if os.path.isfile(logpath):
            logpath = os.path.abspath(logpath)
            for k, v in filesystems.items():
                if v.logpath == logpath:
                    return v
        return None
    
    filesystems = get_filesystems(defaults)
    fs = None
    mount_info = None
    path = '/'
    # name:/path or logpath:/path
    if ':' in arg:
        name = arg.split(':')[0]
        # name:/path
        if name in filesystems:
            fs = filesystems[name]
        # logpath:/path
        else:
            fs = get_from_logpath(filesystems, name)
        if fs:
            path = ':'.join(arg.split(':')[1:])
    # Inside a mountpoint
    if fs is None:
        mount_info = utils.get_mount_info(arg)
        if mount_info:
            logpath = mount_info.logpath
            fs = get_from_logpath(filesystems, logpath)
            path = os.path.abspath(logpath)
            path = re.sub(r'^%s' % mount_info.mountpoint, path, '')
    # name of logpath
    if fs is None:
        # name
        if arg in filesystems:
            fs = filesystems[arg]
        # logpath
        else:
            fs = get_from_logpath(filesystems, arg)
    if fs is None:
        sys.stderr.write("logpath or path?\n")
        sys.exit(2)
    if mount_info is None:
        mount_info = utils.get_mount_info(fs.logpath, logpath=True)
    return utils.AttrDict(
        fs=fs,
        path=path,
        mount_info=mount_info,
    )


def get_filesystems(defaults):
    result = {}
    config = get_or_create_config(defaults)
    for section, content in config.items():
        if section != 'DEFAULT':
            result[section] = utils.AttrDict(
                name=section,
                logpath=os.path.normpath(content['logpath']),
                port=int(content['port']),
            )
    for log in os.listdir(defaults.logdir):
        if log not in result:
            name = log
            result[name] = utils.AttrDict(
                name=section,
                logpath=os.path.normpath(os.path.join(defaults.logdir, log)),
                port=get_port(name),
            )
    return result


def get_default_name(defaults):
    """ get basefs filesystem name if there is only one fs """
    try:
        logs = os.listdir(defaults.logdir)
    except FileNotFoundError:
        sys.stderr.write("Error: logdir '%s' does not exists\n" % defaults.logdir)
        sys.exit(3)
    else:
        if len(logs) == 1:
            name = logs[0]
            return name
        else:
            sys.stderr.write("Error: name should be provided when not running inside a mounted basefs filesystem\n")
            sys.exit(3)


def get_cmd_port(args, mount_info, defaults):
    port = mount_info.port if mount_info else None
    name = args.name
    if not port and not name:
        name = get_default_name(defaults)
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


def reporthook(blocknum, blocksize, totalsize):
    readsofar = blocknum * blocksize
    if totalsize > 0:
        percent = readsofar * 1e2 / totalsize
        s = "\r%5.1f%% %*d / %d" % (
            percent, len(str(totalsize)), readsofar, totalsize)
        sys.stderr.write(s)
        if readsofar >= totalsize: # near the end
            sys.stderr.write("\n")
    else:
        # total size is unknown
        sys.stderr.write("read %d\n" % (readsofar,))
