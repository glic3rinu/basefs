export BASEFSPATH=/home/glic3/Dropbox/basefs/
export PYTHONPATH=$BASEFSPATH


function build () {
    docker build -t basefs $BASEFSPATH
}


function bstop () {
    containers=$(docker ps -a -q)
    if [[ $containers != '' ]]; then
        docker stop -t 0 $containers
        docker rm $containers
    fi
}


function bstart () {
    num=${1:-3}
    if [[ $(whoami) != 'root' ]]; then
        echo "Root permissions are required for running basefs resources"
        exit 3
    fi
    basefs genkey;
    docker_ip=$(ip -f inet -o addr show docker0 | awk {'print $4'} | cut -d'/' -f1)
    basefs bootstrap test -i ${docker_ip} -f;
    basefs resources test -l -r > $BASEFSPATH/tmp/logs/node-0-resources &
    trap "kill $! 2> /dev/null; bstop; kill $$ 2> /dev/null" INT
    for ix in $(seq 1 $num); do
        docker run -v $BASEFSPATH:/mnt --privileged --cap-add SYS_ADMIN --device /dev/fuse -t basefs /bin/bash -c "
            sleep 5;
            basefs genkey;
            basefs get test ${docker_ip};
            basefs resources test -l -r > /mnt/tmp/logs/node-$ix-resources &
            #tc qdisc add dev eth0 root handle 1:0 netem delay 100ms 20ms distribution normal reorder 25% 50% loss 20% 25%;
            #tc qdisc add dev eth0 parent 1:1 handle 10: tbf rate 10mbit buffer 75000 latency 5ms;
            mkdir -p /tmp/test;
            basefs mount test /tmp/test -d &> /mnt/tmp/logs/node-$ix" &
    done
    mkdir -p /tmp/test;
    basefs mount test /tmp/test/ -iface docker0 -d 2>&1 | tee $BASEFSPATH/tmp/logs/node-0
}


function bwrite () {
    size=${1:-1}
    filename=${2:-"/tmp/test/testfile"}
    if [[ $size -eq 1 ]]; then
        fold=300
    else
        fold=470
    fi
    cat /dev/urandom | fold -w $fold | head -n $size > $filename
}


function bread () {
    grep " basefs.messages: Sending " $BASEFSPATH/tmp/logs/node-0 | awk {'print $1 " " $2 " " $(NF-5) " " $(NF)'} | while read line; do
        line=( $line )
        start=$(date -d "${line[0]} ${line[1]} $(date '+%Z')" +'%s.%3N')
        echo "START $start ${line[2]}"
        completed=1
        grep -ah "COMPLETED ${line[3]}" $BASEFSPATH/tmp/logs/node-* | awk {'print $1 " " $2'} | while read line; do
            echo "COMPLETED" $(echo $(date -d "$line UTC" +'%s.%3N')-$start | bc) $completed
            completed=$(($completed+1))
        done
    done
}

function bcsv () {
    echo "Messages,Node,Time"
    for file in "$@"; do
        dir=$(dirname $file)
        grep -ha " basefs.messages: Sending " $file | awk {'print $1 " " $2 " " $(NF-5) " " $(NF)'} | while read line; do
            line=( $line )
            start=$(date -d "${line[0]} ${line[1]} $(date '+%Z')" +'%s.%3N')
            grep -Ta "COMPLETED ${line[3]}" $dir/node-* | awk {'print $1 " " $2 " " $3'} | while read nodeline; do
                nodeline=( $nodeline )
                node=$(echo "${nodeline[0]}" | sed -E "s/.*node-([0-9]+)$/\1/")
                echo ${line[2]},${node},$(echo $(date -d "${nodeline[1]:2} ${nodeline[2]} UTC" +'%s.%3N') $start | awk '{printf "%f", $1 - $2}')
            done
        done
    done
}
