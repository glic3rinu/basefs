export BASEFSPATH=/home/glic3/Dropbox/basefs/
export PYTHONPATH=$BASEFSPATH


function build () {
    docker build -t basefs $BASEFSPATH
}


function bstop () {
    docker stop -t 0 $(docker ps -a -q)
    docker rm $(docker ps -a -q)
}


function bstart () {
    num=1
    if [[ $(whoami) == 'root' ]]; then
        basefs resources test -l -r -u glic3 > $BASEFSPATH/tmp/logs/node-0-resources &
        pid=$!
        trap_content="kill $pid; bstop; kill $$"
        trap "$trap_content" INT
        docker_ip=$(ip -f inet -o addr show docker0 | awk {'print $4'} | cut -d'/' -f1)
        for ix in $(seq 1 $num); do
            docker run -v $BASEFSPATH:/mnt --privileged --cap-add SYS_ADMIN --device /dev/fuse -t basefs /bin/bash -c "
                sleep 5;
                basefs genkey;
                basefs get test ${docker_ip};
                basefs resources test -l -r > /mnt/tmp/logs/node-$ix-resources &
                tc qdisc add dev eth0 root handle 1:0 netem delay 100ms 20ms distribution normal reorder 25% 50% loss 20% 25%;
                tc qdisc add dev eth0 parent 1:1 handle 10: tbf rate 10mbit buffer 75000 latency 5ms;
                mkdir -p /tmp/test;
                basefs mount test /tmp/test -d &> /mnt/tmp/logs/node-$ix" &
        done
        su - glic3 bash -c "
            export PYTHONPATH=$BASEFSPATH
            basefs bootstrap test -i ${docker_ip} -f;
            mkdir -p /tmp/test;
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
