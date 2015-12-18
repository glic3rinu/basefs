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

from basefs import utils
from basefs.config import get_defaults
from basefs.management.utils import get_cmd_port


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
    status = []
    with open('/proc/%s/status' % pid, 'r') as handler:
        for line in handler.readlines():
            line = line.split()
            if line[0] == 'VmSwap:':
                if line[-1] != 'kB':
                    raise ValueError(line[-1])
                status.append(int(line[1])*1000)
            elif line[0] == 'Threads:':
                status.insert(0, int(line[1]))
            elif line[0] == 'voluntary_ctxt_switches:':
                status.insert(1, int(line[1]))
            elif line[0] == 'nonvoluntary_ctxt_switches:':
                status.insert(2, int(line[1]))
    with open('/proc/%s/statm' % pid, 'r') as handler:
        statm = handler.read().split()
    stat = list(map(int, stat[13:15]))
    statm.pop(4)
    statm = list(map(int, statm[:-1]))
    if reset and pid not in offset:
        offset[pid] = stat + status
    if pid not in state:
        state[pid] = stat + status + statm
    prev_state = state[pid]
    state[pid] = stat + status + statm
    result = []
    for ix, s in enumerate(state[pid]):
        result.append(s-(offset[pid][ix] if reset and ix < len(offset[pid])-1 else 0))
        result.append(s-prev_state[ix])
    return result


def get_pids(port):
    netstat = subprocess.Popen('netstat -lntp | grep ":18376 \|:18374 "', shell=True, stdout=subprocess.PIPE)
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


def render(name, time, pid, iptables, proc):
    head = '%s %i' % (name, pid)
    head += '\n' + '-'*len(head)
    for ix, v in list(enumerate(proc)):
        if ix < 4:
            val = float(v)/SC_CLK_TCK
        elif ix > 9:
            if ix > 11:
                v = PAGE_SIZE*v
            val = '' if (not v and ix % 2) else utils.sizeof_fmt(v)
        else:
            val = v
        if ix % 2:
            sign = '+' if v > 0 else ''
            proc[ix] = '%s%s' % (sign, val) if v else ''
        else:
            proc[ix] = val
    for ix, v in list(enumerate(iptables)):
        if ix in (2, 3, 6, 7):
            v = '' if (not v and ix % 2) else utils.sizeof_fmt(v)
        if ix % 2:
            iptables[ix] = '+%s' % v if v else ''
        else:
            iptables[ix] = v
    result = textwrap.dedent("""\
        {head}
         Real\t\t{time:.2f}
         User\t\t{proc[0]} {proc[1]}
         System\t\t{proc[2]} {proc[3]}
        
         Size\t\t{proc[12]} {proc[13]}
         Resident\t{proc[14]} {proc[15]}
         Shared\t\t{proc[16]} {proc[17]}
         Text\t\t{proc[18]} {proc[19]}
         Data\t\t{proc[20]} {proc[21]}
         Swap\t\t{proc[10]} {proc[11]}
         
         Threads\t{proc[4]} {proc[5]}
         VCtxt switches\t{proc[6]} {proc[7]}
         NCtxt switches\t{proc[8]} {proc[9]}
         
        """).format(head=head, time=time, proc=proc)
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


def main(window=None, reset=False, offset=0, port=None):
    first = True
    output = ''
    while True:
        try:
            now = time.time() + offset
            basefs_proc = read_proc(basefs_pid, reset=reset)
            serf_proc = read_proc(serf_pid, reset=reset)
            iptables = read_iptables(port, reset=reset)
            basefs_iptables = iptables[('tcp', port+2)]
            serf_iptables = iptables[('udp', port)] + iptables[('tcp', port)]
            if window:
                output = render('BaseFS', now-basefs_init, basefs_pid, basefs_iptables, basefs_proc)
                output += '\n' + render('Serf', now-serf_init, serf_pid, serf_iptables, serf_proc)
                window.addstr(0, 0, '> Runnig\n\n' + output)
                window.refresh()
            else:
                output = str(now)[:16]
                output += ' basefs:' + ':'.join(map(str, basefs_iptables[::2] + basefs_proc[::2]))
                output += ' serf:' + ':'.join(map(str, serf_iptables[::2] + serf_proc[::2])) + '\n'
                if first:
                    sys.stderr.write(
                        "name:real:user:system:threads:vctxtswitches:nctxtswitches:"
                        "swap:size:resident:shared:text:data:pkts:bytes[:pkts:bytes]\n")
                    first = False
                sys.stdout.write(output)
        except (FileNotFoundError, NameError) as e:
            msg = "> Waitting for BaseFS to go online ...\n"
            if window:
                window.addstr(0, 0, msg + '\n' + output)
                window.refresh()
            else:
                sys.stderr.write(msg)
            # Serf parent is basefs main thread (fuse) and then child is serf's agent
            set_iptables(port)
            pids = get_pids(port)
            if len(pids) == 2:
                basefs_pid, serf_pid = pids
                basefs_init = os.stat('/proc/%i/cmdline' % basefs_pid).st_ctime
                serf_init = os.stat('/proc/%i/cmdline' % serf_pid).st_ctime
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
parser.add_argument('-u', '--user', dest='user',
    help='Username of the actual user that runs the BaseFS filesystem.')


def command():
    if getpass.getuser() != 'root':
        sys.stderr.write("Err. Sorry you need root permissions for using iptables.\n")
        sys.exit(2)
    args = parser.parse_args()
    offset = 0
    if args.ntp_server:
        offset = get_ntp_offset(args.ntp_server)
    mount_info = utils.get_mount_info()
    port = get_cmd_port(args, mount_info, get_defaults(args.user))-2
    main2 = functools.partial(main, reset=args.reset, offset=offset, port=port)
    if not args.log:
        stdscr = curses.initscr()
        curses.curs_set(0)
        try:
            curses.wrapper(main2)
        except KeyboardInterrupt:
            i = 0
            line = stdscr.instr(i, 0)
            while line:
                sys.stdout.write(line.decode()+'\n')
                i += 1
                line = stdscr.instr(i, 0)
    else:
        main2()
