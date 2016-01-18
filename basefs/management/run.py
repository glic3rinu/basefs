import argparse
import logging
import os
import sys

from fuse import FUSE

from basefs import utils, validators, gossip, loop
from basefs.config import get_or_create_config, defaults, get_port
from basefs.fs import FileSystem
from basefs.keys import Key
from basefs.logs import Log
from basefs.views import View


parser = argparse.ArgumentParser(
    description='Run an existing filesystem without mounting it (testing)',
    prog='basefs run')


def set_parser(parser):
    # TODO make validators.name_or_logpath return (name, logpath) tuple for DRY-ines
    parser.add_argument('logpath',
        type=validators.name_or_logpath(parser, get_or_create_config(defaults), defaults),
        help='Log name or logpath')
    parser.add_argument('-k', '--keys', dest='keypath',
        default=defaults.keypath,
        help='Path to the EC private key. %s by default. Use genkey for creating one.' % defaults.keypath,
        type=validators.file_exists(parser, name='keypath'))
    parser.add_argument('-j', '--join', dest='join',
        help='comma separated ip:port used as boostrapping nodes.')
    parser.add_argument('-b', '--bind', dest='bind', default='0.0.0.0',
        help='Basefs bind including: serf agent, serf client (port+1) and basefs server(port+2)')
    parser.add_argument('-iface', dest='iface',
        help='Network interface to bind to. Can be used instead of -bind if the interface is known '
             'but not the address.')
    parser.add_argument('-H', '--hostname', dest='hostname',
        help='Name of this node. Must be unique in the cluster.')
    parser.add_argument('-d', '--debug', dest='debug', action='store_true',
        help='Enables debugging information.')
    parser.add_argument('-s', '--single-node', dest='serf', action='store_false',
        help='Disables Serf agent (testing purposes).')
    parser.add_argument('-w', '--watcher', dest='watcher',
        help='Handler script executed when a change occur on the filesystem (inotify substitute).')
    parser.add_argument('-f', '--foreground', dest='foreground', action='store_true', default=False,
        help='Stays in foreground.')


def command(mount=False, arg_parser=None):
    if arg_parser is None:
        set_parser(parser)
        arg_parser = parser
    args = arg_parser.parse_args()
    ip, *port = args.bind.split(':')
    if port:
        port = int(port[0])
    if args.iface:
        iface_ip = utils.get_ip_address(args.iface)
        if ip != '0.0.0.0' and ip != iface_ip:
            sys.stderr.write("-bind and -iface ip addresses do not match %s != %s\n" % (ip, iface_ip))
            sys.exit(9)
        ip = iface_ip
    logpath = args.logpath
    config = get_or_create_config(defaults)
    section = None
    hostname = args.hostname
    if logpath in config:
        section = config[args.logpath]
        logpath = section['logpath']
        if not port:
            port = int(section['port'])
        if not hostname:
            hostname = section.get('hostname', '')
    elif not os.path.exists(logpath) and os.path.exists(os.path.join(defaults.logdir, logpath)):
        if not port:
            port = get_port(logpath)
        logpath = os.path.join(defaults.logdir, logpath)
    elif not port:
        port = 7372
    if not hostname:
        hostname = defaults.hostname
    rpc_port = port+1
    sync_port = port+2
    logpath = os.path.normpath(logpath)
    info, point = utils.get_mountpoint(logpath)
    if info:
        sys.stderr.write("Error: log %s already mounted in %s\n" % (logpath, point))
        sys.exit(4)
    keypath = os.path.normpath(args.keypath)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)-15s [%(levelname)s] %(name)s: %(message)s',
    )
    logpath = os.path.normpath(logpath)
    log = Log(logpath)
    log.load()
    if keypath == defaults.keypath and not os.path.exists(keypath):
        view = View(log)
    else:
        key = Key.load(keypath)
        view = View(log, key)
    view.build()
    serf = None
    serf_agent = None
    if args.serf:
        join = args.join.split(',') if args.join else []
        serf, serf_agent = gossip.run(section, view, ip, port, hostname, join)
        if args.watcher:
            handler = handlers.Handler(args.watcher, view.log, state=serf.blockstate)
    else:
        if args.watcher:
            handler = handlers.Handler(args.watcher, view.log)
    if mount:
        init_function = lambda: None
        if args.serf:
            # Eventloop needs to run on a separated thread when using FUSE
            init_function = lambda: loop.run_thread(view, serf, port+2, config=section)
        mountpoint = args.mountpoint
        sys.stdout.write('Mounting %s into %s\n' % (logpath, mountpoint))
        fs = FileSystem(view, serf=serf, serf_agent=serf_agent, init_function=init_function)
        fsname = '%s:%i' % (logpath, sync_port)
        foreground = args.foreground or args.debug
        FUSE(fs, mountpoint, fsname=fsname, nothreads=False, foreground=foreground)
    else:
        try:
            loop.run(view, serf, port+2, config=section)
        except KeyboardInterrupt:
            pass
        finally:
            serf_agent.stop()
