import argparse
import ipaddress
import os
import subprocess
import sys

from basefs import utils
from basefs.config import get_port, defaults
from basefs.logs import Log
from basefs.management.utils import create_logdir


parser = argparse.ArgumentParser(
    description="Get log from peer address",
    prog='basefs get')
parser.add_argument('name')
parser.add_argument('addr',
    help='ip[:port] or domain name')
parser.add_argument('-l', '--logpath', dest='logpath',
    help='Path to the basefs log file, use - for stdout.')
parser.add_argument('-f', '--force', dest='force', action='store_true',
    help='Rewrite log file if present')


def command():
    # get <domainTXT/domain:port/ip:port> [-l <logpath>] [-n <name>] [-p] [-f] [-d]
    args = parser.parse_args()
    default_logpath = os.path.join(defaults.dir, 'logs', args.name)
    logpath = args.logpath or default_logpath
    if logpath != '-':
        create_logdir(logpath, default_logpath, args.force)
    ip, *port = args.addr.split(':')
    try:
        ip = str(ipaddress.ip_address(ip))
    except ValueError:
        nslookup = """nslookup -q=txt %s|grep 'text =' | sed -E 's/.*text = "([^"]+)".*/\\1/'""" % ip
        lookup = subprocess.Popen(nslookup, shell=True, stdout=subprocess.PIPE)
        lookup = lookup.stdout.read().decode().strip()
        if lookup:
            ip, *port = lookup.split(':')
        else:
            nslookup = "nslookup %s -q=a | grep Address|tail -n1 | awk {'print $2'}" % ip
            lookup = subprocess.Popen(nslookup, shell=True, stdout=subprocess.PIPE)
            lookup = lookup.stdout.read().decode().strip()
            if not '#' in lookup:
                ip = lookup
    if not port:
        port = get_port(args.name) + 2
    else:
        port = int(port[0])
    sys.stderr.write("Connecting to %s:%i\n" % (ip, port))
    received = False
    if logpath == '-':
        for data in utils.netcat(ip, port, b'cGET'):
            sys.stdout.write(data)
            received = True
    else:
        try:
            with open(logpath, 'w') as handler:
                for data in utils.netcat(ip, port, b'cGET'):
                    handler.write(data)
                    received = True
        except ConnectionRefusedError:
            os.remove(logpath)
            sys.stderr.write("Error: connection refused, bad port?\n")
            sys.exit(3)
    if not received:
        sys.stderr.write("Error: nothing has been received, bad port?\n")
        sys.exit(2)
    elif logpath != '-':
        log = Log(logpath)
        try:
            log.load(validate=True)
        except exceptions.ValidationError as e:
            sys.stderr.write(str(e) + '\n')
        sys.stdout.write("%s log created\n" % logpath)
