#!/bin/bash

if [[ -e /home/glic3/Dropbox/basefs/ ]]; then
    export BASEFSPATH=/home/glic3/Dropbox/basefs/
    export CONFINEIP=$(ssh root@calmisko.org ifconfig tap0 | grep "inet addr:"|awk {'print $2'}|cut -d':' -f2)
else
    export BASEFSPATH=/root/basefs/
    export CONFINEIP=$(ip addr|grep tap0|grep inet|sed -E "s#.* inet ([^/]+)/.*#\1#")
fi
export PYTHONPATH=$BASEFSPATH
export PATH=$PATH:$(realpath $BASEFSPATH/eval/confine/src)
[[ "$CONFINEIP" == "" ]] && echo "CONFINEIP not set"
cd $BASEFSPATH/eval/confine


function replace () {
    rm -fr $2
    cp -r $1 $2
    rm -fr $1
}


function runconfineexperiment () {
    openntpd -f /etc/ntpd.conf
    sed -i "s/^    MAX_BLOCK_MESSAGES = [0-9].*/    MAX_BLOCK_MESSAGES = 10/" /root/basefs/basefs/gossip.py
    sed -i "s/^    FULL_SYNC_INTERVAL = [0-9].*/    FULL_SYNC_INTERVAL = 20/" /root/basefs/basefs/sync.py
    basefs genkey;
    basefs bootstrap test -i $CONFINEIP -f;
    basefs resources test -l -r > $BASEFSPATH/tmp/logs/node-0-resources &
    echo "Staring $(date)" > /tmp/eval_conv
    mkdir -p $BASEFSPATH/tmp/logs
    echo "$cmd" "$nodes"
    mkdir -p /tmp/test;
    { 
        basefs mount test /tmp/test/ -iface tap0 -d 2>&1 | tee $BASEFSPATH/tmp/logs/node-0
    } &
    sleep 2
    pid=$!
    cpid=$(pgrep -P $pid basefs)
    trap "kill -INT $cpid; kill $pid 2> /dev/null; killall basefs; kill $$ 2> /dev/null; kill $cpid; run bash experiment -s;" INT
    echo "$(date) put experiment" >> /tmp/eval_conv
    put experiment
    echo "$(date) run experiment" >> /tmp/eval_conv
    run bash experiment -r $CONFINEIP &
    echo "$(date) sleep 20" >> /tmp/eval_conv
    sleep 20
    repetitions=${2:-20}
    rounds=( 0 0 1 16 0 0 0 0 2 1 4 1 0 0 1 0 0 1 1 0 0 0 1 1 0 0 0 0 )
    counter=0
    ones=0
    twos=0
    fours=0
    sixteens=0
    for i in $(seq 1 $repetitions); do
        echo "$(date) Repetition $i" >> /tmp/eval_conv
        sleep 10
        for j in ${rounds[@]}; do
            # CP and sleep for 6 seconds
            case $j in
                0)
                    origin=$BASEFSPATH/tmp/testpoint/testfile-1
                    ;;
                1)
                    origin=$BASEFSPATH/tmp/testpoint/testfile-1-$ones
                    ones=$(($ones+1))
                    ;;
                2)
                    origin=$BASEFSPATH/tmp/testpoint/testfile-2-$twos
                    twos=$(($twos+1))
                    ;;
                4)
                    origin=$BASEFSPATH/tmp/testpoint/testfile-4-$fours
                    fours=$(($fours+1))
                    ;;
                16)
                    origin=$BASEFSPATH/tmp/testpoint/testfile-16-$sixteens
                    sixteens=$(($sixteens+1))
                    ;;
            esac
            echo "$(date) cp $origin /tmp/test/testfile$counter-$i-$j" >> /tmp/eval_status
            cp $origin /tmp/test/testfile$counter-$i-$j
            sleep 3
            uid=$(grep " basefs.fs: Sending entry " $BASEFSPATH/tmp/logs/node-0 | tail -n 1 | sed -E "s#([^:]+)\s*2016/01/.*2016-01-#\12016-01-#" | awk {'print $7'})
            echo "UID $uid" >> /tmp/eval_conv
            sleep 3
            counter=$(($counter+1))
        done
    done
    echo "$(date) DONE waitting to finish, sleep 400" >> /tmp/eval_conv
    sleep 400
    kill -INT $(ps aux|grep '/usr/local/bin/basefs mount test /tmp/test/'|awk {'print $2'}|head -n 1)
    run bash experiment -s
    sleep 20
    kill -INT $(ps aux|grep '/usr/local/bin/basefs mount test /tmp/test/'|awk {'print $2'}|head -n 1)
    run bash experiment -s
    sleep 20
    killall basefs
    echo "Ending $(date)" >> /tmp/eval_conv
    trap - INT
}


runconfineexperiment
