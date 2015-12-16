export -f BASEFSPATH=/home/glic3/Dropbox/basefs/
export -f PYTHONPATH=$BASEFSPATH


function build () {
    docker build -t basefs $BASEFSPATH
}

function bstop () {
    docker stop -t 0 $(docker ps -a -q)
    docker rm $(docker ps -a -q)
}


function bstart () {
    if [[ $(whoami) == 'root' ]]; then
        iptables -D OUTPUT -p udp --sport 18374 -j LOG
        iptables -D OUTPUT -p tcp --sport 18374 -j LOG
        iptables -D OUTPUT -p tcp --sport 18376 -j LOG
        iptables -A OUTPUT -p udp --sport 18374 -j LOG
        iptables -A OUTPUT -p tcp --sport 18374 -j LOG
        iptables -A OUTPUT -p tcp --sport 18376 -j LOG
        {
            echo -n '' > /tmp/traffic
            while true; do
                result=""
                while read line; do
                    result="${result}$line "
                done < <(iptables -n -L -v | grep "LOG .* spt:" | awk {'split($11, port, ":"); print $10":"port[2]":"$1":"$2'})
                echo $(date '+%s' -d "+ $offset seconds") "$result" >> /mnt/tmp/logs/node-0-traffic
                sleep 1;
            done
        } &
        pid=$!
        trap "kill $pid; bstop;" INT
        for ix in $(seq 1 3); do
            docker run -v $BASEFSPATH:/mnt --privileged --cap-add SYS_ADMIN --device /dev/fuse -t basefs cat << EOF | /bin/bash
                sleep 1
                iptables -D OUTPUT -p udp --sport 18374 -j LOG
                iptables -D OUTPUT -p tcp --sport 18374 -j LOG
                iptables -D OUTPUT -p tcp --sport 18376 -j LOG
                iptables -A OUTPUT -p udp --sport 18374 -j LOG
                iptables -A OUTPUT -p tcp --sport 18374 -j LOG
                iptables -A OUTPUT -p tcp --sport 18376 -j LOG
                {
                    echo -n '' > /tmp/traffic
                    while true; do
                        result=""
                        while read line; do
                            result="\${result}\$line "
                        done < <(iptables -n -L -v | grep "LOG .* spt:" | awk {'split(\$11, port, ":"); print \$10":"port[2]":"\$1":"\$2'})
                        echo \$(date '+%s' -d "+ \$offset seconds") "\$result" >> /mnt/tmp/logs/node-$ix-traffic
                        sleep 1;
                    done
                } &
                /mnt/basefs/bin/basefs genkey;
                basefs get test 172.17.0.1;
                tc qdisc add dev eth0 root handle 1:0 netem delay 100ms 20ms distribution normal reorder 25% 50% loss 20% 25%;
                tc qdisc add dev eth0 parent 1:1 handle 10: tbf rate 10mbit buffer 75000 latency 5ms;
                mkdir /tmp/test;
                basefs mount test /tmp/test -d &> /mnt/tmp/logs/node-$ix &
EOF
        done
        su - glic3rinu bash -c "
            basefs bootstrap test -i 172.17.0.1 -f;
            mkdir /tmp/test;
            basefs mount test /tmp/test/ -d 2>&1 | tee $BASEFSPATH/tmp/logs/node-0"
    fi
}


function bwrite () {
    size=${1:-1}
    cat /dev/urandom | fold -w 470 | head -n $size > /tmp/test/testfile
}

function bread () {
    entryhash=$(basefs show test | grep " testfile " | tail -n1 | awk {'print $(NF-2)'})
    start=$(grep -ah "release /testfile" $BASEFSPATH/tmp/logs/node-0 | tail -n1 | awk {'print $1 " " $2'})
    start=$(date -d "$start $(date '+%Z')" +'%s.%3N')
    echo "START" $start
    grep -ah "COMPLETED $entryhash" $BASEFSPATH/tmp/logs/node-* | awk {'print $1 " " $2'} | while read line; do
        echo "COMPLETED" $(echo $(date -d "$line UTC" +'%s.%3N')-$start | bc)
    done
}
