import argparse
import os
import sys

from basefs.config import get_or_create_config, defaults, get_port
from basefs.keys import Key
from basefs.logs import Log

from . import utils


parser = argparse.ArgumentParser(
    description='Create a new self-contained filesystem',
    prog='basefs bootstrap')
parser.add_argument('name',
    help='Name')
parser.add_argument('-i', '--ips', dest='ips', required=True,
    help='Comma separated ip[:<port>] used as boostrapping nodes.')
parser.add_argument('-p', '--port', dest='port',
    help='Default port.')
parser.add_argument('-l', '--logpath',
    help='Path to the basefs log file')
parser.add_argument('-k', '--keys', dest='keypaths',
    default=defaults.keypath,
    help='Comma separated list of paths containing the root keys. %s by default.' % defaults.keypath)
parser.add_argument('-f', '--force', dest='force', action='store_true',
    help='Rewrite log file if present')


def command():
    # bootsrap <name> -i <ip>[:<port>] [-l <logpath>] [-k <keypath>] [-f]
    args = parser.parse_args()
    default_logpath = os.path.join(defaults.dir, 'logs', args.name)
    logpath = args.logpath or default_logpath
    port = args.port or get_port(args.name)
    utils.create_logdir(logpath, default_logpath, args.force)
    keys = []
    for keypath in args.keypaths.split(','):
        if not os.path.isfile(keypath):
            sys.stderr.write("Error: bootsraping keypath %s does not exist.\n" % keypath)
            sys.exit(2)
        keys.append(Key.load(keypath))
    log = Log(logpath) # TODO, name=args.name)
    ips = []
    for ip in args.ips.split(','):
        if ':' not in ip:
            ip += ':%i' % port
        ips.append(ip)
    log.bootstrap(keys, ips)
    config = get_or_create_config(defaults)
    if args.name not in config:
        config[args.name] = {}
    config[args.name].update({
        'logpath': logpath,
        'port': str(port),
    })
    config.save()
    sys.stdout.write('Created log file %s\n' % logpath)
    sys.stdout.write('Network bootstraping will happen at:\n  %s\n' % '\n  '.join(ips))
    sys.exit(0)

