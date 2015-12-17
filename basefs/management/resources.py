import argparse
import curses
import functools
import getpass
import os
import resource
import sys
import subprocess
import textwrap
import time
from collections import OrderedDict
from operator import sub

from basefs.utils import sizeof_fmt


"""
/proc/[pid]/stat
      (14) utime  %lu
                Amount of time that this process has been scheduled
                in user mode, measured in clock ticks (divide by
                sysconf(_SC_CLK_TCK)).  This includes guest time,
                guest_time (time spent running a virtual CPU, see
                below), so that applications that are not aware of
                the guest time field do not lose that time from
                their calculations.
      (15) stime  %lu
                Amount of time that this process has been scheduled
                in kernel mode, measured in clock ticks (divide by
                sysconf(_SC_CLK_TCK)).
      (16) cutime  %ld
                Amount of time that this process's waited-for
                children have been scheduled in user mode, measured
                in clock ticks (divide by sysconf(_SC_CLK_TCK)).
                (See also times(2).)  This includes guest time,
                cguest_time (time spent running a virtual CPU, see
                below).
      (17) cstime  %ld
                Amount of time that this process's waited-for
                children have been scheduled in kernel mode,
                measured in clock ticks (divide by
                sysconf(_SC_CLK_TCK)).
/proc/[pid]/statm
      Provides information about memory usage, measured in pages.
      The columns are:
          size       (1) total program size
                     (same as VmSize in /proc/[pid]/status)
          resident   (2) resident set size
                     (same as VmRSS in /proc/[pid]/status)
          share      (3) shared pages (i.e., backed by a file)
          text       (4) text (code)
          lib        (5) library (unused in Linux 2.6)
          data       (6) data + stack
          dt         (7) dirty pages (unused in Linux 2.6)
"""


SC_CLK_TCK = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
PAGE_SIZE = resource.getpagesize()


def get_ntp_offset(server):
    ntp = subprocess.Popen("ntpdate -d %s | grep 'offset ' | awk {'print $2'} | head -n1" % server,
        shell=True, stdout=subprocess.PIPE)
    return float(ntp.stdout.read().decode().strip())


def set_iptables(port):
    os.system("""
        if ! iptables -n -L OUTPUT | grep ' udp spt:%(serf_port)s ' > /dev/null; then
            iptables -A OUTPUT -p udp --sport %(serf_port)s -j LOG;
            iptables -A OUTPUT -p tcp --sport %(serf_port)s -j LOG;
            iptables -A OUTPUT -p tcp --sport %(sync_port)s -j LOG;
        fi
        """ % {
            'serf_port': port,
            'sync_port': port+2
        })


def to_int(value):
    conversion = {
        'K': 1000,
        'M': 1000000,
        'G': 1000000000,
        'T': 1000000000000,
    }
    if value.endswith(('K', 'M', 'G', 'T')):
        return int(value[:-1])*conversion[value[-1]]
    return int(value)


def read_iptables(port, state={}, offset={}, reset=False):
    iptables = subprocess.Popen('iptables -n -L OUTPUT -v', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stderr = iptables.stderr.read()
    if stderr:
        sys.stderr.buffer.write(stderr)
        sys.exit(3)
    result = {}
    inspected = []
    for line in iptables.stdout.readlines():
        line = line.decode().split()
        if line[0].isdigit():
            iport = line[10]
            flow, iport = iport.split(':')
            iport = int(iport)
            if iport in (port, port+2) and flow == 'spt':
                pkts, bytes = map(to_int, line[:2])
                prot = line[3]
                if (prot, iport) not in inspected:
                    if reset and (prot, iport) not in offset:
                        offset[(prot, iport)] = (pkts, bytes)
                    if (prot, iport) not in state:
                        state[(prot, iport)] = (pkts, bytes)
                    c_offset = offset.get((prot, iport), [0,0])
                    prev_pkts, prev_bytes = state[(prot, iport)]
                    result[(prot, iport)] = [pkts-c_offset[0], pkts-prev_pkts, bytes-c_offset[1], bytes-prev_bytes]
                    state[(prot, iport)] = (pkts, bytes)
                    inspected.append((prot, iport))
    return result


def read_proc(pid, state={}, offset={}, reset=False):
    with open('/proc/%s/stat' % pid, 'r') as handler:
        stat = handler.read().split()
    with open('/proc/%s/statm' % pid, 'r') as handler:
        statm = handler.read().split()
    stat = list(map(int, stat[13:17]))
    statm = list(map(int, statm))
    real = sum(stat)
    if reset and pid not in offset:
        offset[pid] = [real] + stat
    if pid not in state:
        state[pid] = [real] + stat + statm
    prev_state = state[pid]
    state[pid] = [real] + stat + statm
    result = []
    for ix,s in enumerate(state[pid]):
        result.append(s-(offset[pid][ix] if reset and ix < 5 else 0))
        result.append(s-prev_state[ix])
    return result


def get_pids(port):
    netstat = subprocess.Popen('netstat -lntp|grep ":18376 \|:18374 "', shell=True, stdout=subprocess.PIPE)
    pids = []
    for line in netstat.stdout.readlines():
        proc = line.decode().split()[-1]
        pid, name = proc.split('/')
        if name == 'serf':
            pids.append(int(pid))
        elif name.startswith('py'):
            pids.insert(0, int(pid))
        else:
            raise ValueError(name)
    return pids


def render(name, pid, iptables, proc):
    head = '%s %i' % (name, pid)
    head += '\n' + '-'*len(head)
    for ix, v in list(enumerate(proc)):
        if ix < 10:
            v = float(v)/SC_CLK_TCK
        else:
            v = '' if (not v and ix % 2) else sizeof_fmt(PAGE_SIZE*v)
        if ix % 2:
            proc[ix] = '+%s' % v if v else ''
        else:
            proc[ix] = v
    for ix, v in list(enumerate(iptables)):
        if ix in (2, 3, 6, 7):
            v = '' if (not v and ix % 2) else sizeof_fmt(v)
        if ix % 2:
            iptables[ix] = '+%s' % v if v else ''
        else:
            iptables[ix] = v
    result = textwrap.dedent("""\
        {head}
         Real\t\t{proc[0]} {proc[1]}
         User\t\t{proc[2]} {proc[3]}
         System\t\t{proc[4]} {proc[5]}
        
         Size\t\t{proc[10]} {proc[11]}
         Resident\t{proc[12]} {proc[13]}
         Shared\t\t{proc[14]} {proc[15]}
         Text\t\t{proc[16]} {proc[17]}
         Lib\t\t{proc[18]} {proc[19]}
         Data\t\t{proc[20]} {proc[21]}
         
        """).format(head=head, proc=proc)
    if name.lower() == 'basefs':
        result += textwrap.dedent("""\
             ?Sync pkts\t{iptables[0]} {iptables[1]}
             ?Sync bytes\t{iptables[2]} {iptables[3]}
             """).format(iptables=iptables).replace('?', ' ')
    else:
        result += textwrap.dedent("""\
             ?Gossip pkts\t{iptables[0]} {iptables[1]}
             ?Gossip bytes\t{iptables[2]} {iptables[3]}
             ?Sync pkts\t{iptables[4]} {iptables[5]}
             ?Sync bytes\t{iptables[6]} {iptables[7]}
             """).format(iptables=iptables).replace('?', ' ')
    return result


def main(window=None, reset=False, offset=0):
    while True:
        try:
            timestamp = str(time.time() + offset)[:16]
            iptables = read_iptables(port, reset=reset)
            basefs_iptables = iptables[('tcp', port+2)]
            basefs_proc = read_proc(basefs_pid, reset=reset)
            serf_iptables = iptables[('udp', port)] + iptables[('tcp', port)]
            serf_proc = read_proc(serf_pid, reset=reset)
            if window:
                output = render('BaseFS', basefs_pid, basefs_iptables, basefs_proc)
                output += '\n' + render('Serf', serf_pid, serf_iptables, serf_proc)
                window.addstr(0, 0, output)
                window.refresh()
            else:
                output = timestamp
                output += ' basefs:' + ':'.join(map(str, basefs_iptables[::2] + basefs_proc[::2]))
                output += ' serf:' + ':'.join(map(str, serf_iptables[::2] + serf_proc[::2])) + '\n'
                sys.stdout.write(output)
        except (FileNotFoundError, NameError) as e:
            if window:
                window.addstr(0, 0, "Waitting for BaseFS to go online ...\n   " + str(e) +'\n' )
                window.refresh()
            # Serf parent is basefs main thread (fuse) and then child is serf's agent
            port = 18374
            set_iptables(port)
            basefs_pid, serf_pid = get_pids(port)
            iptables = {}
        finally:
            time.sleep(1)


parser = argparse.ArgumentParser(
    description="Display BaseFS resource consumption in real-time",
    prog='basefs resources')
parser.add_argument('name', nargs='?', help='Name')
parser.add_argument('-l', '--log', dest='log', action='store_true',
    help='Log format')
parser.add_argument('-r', '--reset', dest='reset', action='store_true',
    help='Reset resource counters')
parser.add_argument('-n', '--ntp', dest='ntp_server',
    help='NTP server for time synchronization')


def command():
    if getpass.getuser() != 'root':
        sys.stderr.write("Err. Sorry you need root permissions for using iptables.\n")
        sys.exit(2)
    args = parser.parse_args()
    offset = 0
    if args.ntp_server:
        offset = get_ntp_offset(args.ntp_server)
    main2 = functools.partial(main, reset=args.reset, offset=offset)
    if not args.log:
        stdscr = curses.initscr()
        try:
            curses.wrapper(main2)
        except KeyboardInterrupt:
            pass
    else:
        main2()
