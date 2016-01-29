#!/bin/bash

if [[ -e /home/glic3/Dropbox/basefs/ ]]; then
    export BASEFSPATH=/home/glic3/Dropbox/basefs/
else
    export BASEFSPATH=/root/basefs/
fi
export PYTHONPATH=$BASEFSPATH


function readscenarios () {
    echo "scenario,size,messages,node,time,filename,completed"
    echo "scenario,size,messages,filename,completed" >&2
    name=${1:-"scenario"}
    for scenario in $(ls -d ${name}-* 2> /dev/null || ls -d ${name}); do
        scenario_name=$(echo "$scenario" | sed "s/$name-//")
        for log in $(ls  -d $BASEFSPATH/tmp/$scenario/logs-*); do
            grep " basefs.fs: Sending entry " $log/node-0 | sed -E "s#([^:]+)\s*2016/01/.*2016-01-#\12016-01-#" | awk {'print $1 " " $2 " " $(NF-1) " " $NF'} | while read line; do
                line=( $line )
                messages=$(grep " basefs.gossip: Sending .* ${line[2]}" $log/node-0 | sed -E "s#([^:]+)\s*2016/01/.*2016-01-#\12016-01-#" | awk {'print $(NF-5)'})
                messages=${messages:-"-1"}
                start=$(date -d "${line[0]} ${line[1]} $(date '+%Z')" +'%s.%3N' || echo "$line" >&2)
                size=$(echo ${line[3]} | sed -E "s/.*-([0-9]+)'/\1/")
                filename=$(echo ${line[3]} | sed -E "s/'([^']+)'/\1/")
                output=""
                while read nodeline; do
                    linedate="$(echo $nodeline | cut -d':' -f2 | awk {'print $1'}) $(echo $nodeline | awk {'print $2'})"
                    node=$(echo "$nodeline" | cut -d':' -f1)
                    node=${node##*/}
                    complition_time=$(echo $(date -d "$linedate UTC" +'%s.%3N' || echo "$nodeline ${line[2]}" >&2)-$start | bc | awk '{printf "%f\n", $0}')
                    output="$output$complition_time $scenario_name,${size},$messages,$node,$complition_time,$filename\n"
                done < <(grep -a "COMPLETED ${line[2]}" $log/node-* | sed -E "s#([^:]+)\s*2016/01/.*2016-01-#\12016-01-#"| sed "s/:.*2016-01/:2016-01/" | awk {'print $1 " " $2'})
                completed=1
                while read line; do
                    echo $line,$completed
                    completed=$(($completed+1))
                done < <(echo -ne "$output" | sort -n | awk {'print $2'})
                echo $scenario_name,${size},$messages,$filename,$completed >&2
            done
        done
    done
}


function readtotaltraffic () {
    echo "scenario,node,bps"
    name=${1:-"scenario"}
    for scenario in $(ls -d ${name}-*); do
        scenario_name=$(echo "$scenario" | sed "s/$name-//")
        size=${scenario//*-}
        for log in $(ls  -d $BASEFSPATH/tmp/$scenario/logs-*); do
            for node in $(ls $log/node-*-resources); do
                ini=$(head -n1 $node | awk {'print $1'})
                end=$(tail -n1 $node | awk {'print $1'})
                traffic=$(tail -n1 $node | awk {'print $2'} | cut -d':' -f14)
                node_name=$(echo "$node" | sed -E "s#.*/(node-[0-9]+)-resources#\1#")
                echo $scenario_name,$node_name,$(echo "$traffic/($end-$ini)" | bc)
            done
        done
    done
}


function readtraffic () {
cat << 'EOF' | python3 - $@
import os
import re
import statistics
import sys
import tempfile
import textwrap
import subprocess
import glob

port = 18374
serf_udp, serf_tcp, sync = 0, 2, 4
dataset = {}
total_bytes = {}

for filename in sys.argv[1:]:
    with open(filename, 'r') as handler:
        prev = [0, 0, 0, 0, 0, 0]
        result = [0, 0, 0, 0, 0, 0]
        for line in handler:
            # name:user:system:threads:vctxtswitches:nctxtswitches:swap:size:resident:shared:text:data:pkts:bytes[:pkts:bytes]
            # 1450808755.89306 basefs:0:0:43:0:7:325:87:0:119146:4890:1165:726:97825 serf:0:0:0:0:4:0:7:114:40:0:3160:1404:986:989:1041
            # 1449830028.574 udp:18374:0:0
            timestamp, basefs, serf = line.split()
            data = (
                (serf_udp, serf.split(':')[-4:-2]),
                (serf_tcp, serf.split(':')[-2:]),
                (sync, basefs.split(':')[-2:]),
            )
            
            for protocol, values in data:
                pkts, bytes = map(int, values)
                result[protocol] = pkts - prev[protocol]
                result[protocol+1] = bytes - prev[protocol+1]
                prev[protocol] = pkts
                prev[protocol+1] = bytes
            try:
                aggregate = dataset[timestamp]
            except KeyError:
                aggregate = [0, 0, 0, 0, 0, 0]
            dataset[timestamp] = [r+a for r,a in zip(result, aggregate)]
    
    # Last traffic value is the total one
    node = re.findall(r'.*-([0-9]+)-.*', filename)[0]
    try:
        total_bytes[node].append((prev[1], prev[3], prev[5]))
    except KeyError:
        total_bytes[node] = [(prev[1], prev[3], prev[5])]


sys.stdout.write("Timestamp,Serf UDP pkts,Serf UDP bytes,Serf TCP pkts,Serf TCP bytes,Sync pkts,Sync bytes\n")
for k, v in dataset.items():
    sys.stdout.write(','.join([k] + list(map(str, v)))+'\n')


sys.stderr.write("Node,Serf UDP bytes,Serf TCP bytes,Sync bytes\n")
for k in sorted(total_bytes.keys()):
    v = [0, 0, 0]
    for ix in (0, 1, 2):
        v[ix] = statistics.mean([b[ix] for b in total_bytes[k]])
    sys.stderr.write(','.join([k] + list(map(str, v)))+'\n')

EOF
}



function readperformance () {
    echo "fs,operation,round,time"
    num=1
    grep real perf/basefs-write | awk {'print $2'} | sed -e "s/m/*60+/" -e "s/s//" | bc | awk '{printf "%f\n", $0}' | while read line; do
        echo "basefs,write,$num,$line";
        num=$(($num+1));
    done
    num=1
    grep real perf/basefs-read | awk {'print $2'} | sed -e "s/m/*60+/" -e "s/s//" | bc | awk '{printf "%f\n", $0}' | while read line; do
        echo "basefs,read,$num,$line";
        num=$(($num+1));
    done
    num=1
    grep real perf/basefs-read2 | awk {'print $2'} | sed -e "s/m/*60+/" -e "s/s//" | bc | awk '{printf "%f\n", $0}' | while read line; do
        echo "basefs,read-cached,$num,$line";
        num=$(($num+1));
    done

    num=1
    grep real perf/ext4-write | awk {'print $2'} | sed -e "s/m/*60+/" -e "s/s//" | bc | awk '{printf "%f\n", $0}' | while read line; do
        echo "ext4,write,$num,$line";
        num=$(($num+1));
    done
    num=1
    grep real perf/ext4-read | awk {'print $2'} | sed -e "s/m/*60+/" -e "s/s//" | bc | awk '{printf "%f\n", $0}' | while read line; do
        echo "ext4,read,$num,$line";
        num=$(($num+1));
    done
    num=1
    grep real perf/ext4-read2 | awk {'print $2'} | sed -e "s/m/*60+/" -e "s/s//" | bc | awk '{printf "%f\n", $0}' | while read line; do
        echo "ext4,read-cached,$num,$line";
        num=$(($num+1));
    done
}


$1
