#!/bin/bash


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


function etc_chr () {
    basefs bootstrap -i 127.0.0.1 etc_chr 2> /dev/null && {
        mkdir -p /tmp/etc_chr
        basefs mount etc_chr /tmp/etc_chr -s -f &
        sleep 2
        time cp -r /etc /tmp/etc_chr
        killall basefs
    }
    echo "/etc characteristics"
    echo "--------------------"
    echo Directories: $(find /etc -type d | wc -l)
    echo Files: $(find /etc -type f | wc -l)
    echo Links: $(find /etc -type l | wc -l)
    echo Total objects: $(find /etc | wc -l)
    echo Size: $(du -hs /etc)
    echo Log size: $(du -hs /root/.basefs/logs/etc_chr | awk {'print $1'})
    echo Log objects: $(grep -v "^B " /root/.basefs/logs/etc_chr | wc -l)
    echo Log blocks: $(grep "^B " /root/.basefs/logs/etc_chr | wc -l)
    echo Log lines: $(wc -l /root/.basefs/logs/etc_chr | awk {'print $1'})
    for ix in $(seq 0 20); do
        messages=0;
        while read line; do
            line=( $line );
            if [[ ${line[1]} != "B" ]]; then
                messages=$(($messages+${line[0]}));
            elif [[ ${line[0]} -le $ix ]]; then
                messages=$(($messages+${line[0]}));
            fi;
        done < <(cat /root/.basefs/logs/etc_chr | cut -c 1|uniq -c);
        echo "Messages ($ix gossiped blocks): $messages"
    done
}


function dock () {
    if [[ $(whoami) != 'root' ]]; then
        echo "Root permissions are required for running basefs resources"
        exit 3
    fi
    # Docker has to be restarted to renew IP addresses
    service docker restart
    sleep 2
    basefs genkey;
    docker_ip=$(ip -f inet -o addr show docker0 | awk {'print $4'} | cut -d'/' -f1)
    basefs bootstrap test -i ${docker_ip} -f;
    if [[ ${3:-true} == true ]]; then
        basefs resources test -l -r > $BASEFSPATH/tmp/logs/node-0-resources &
    fi
    cmd="$1"
    if [[ "$cmd" == "" || $(echo "$cmd" | grep '^[0-9][0-9]*') ]]; then
        cmd='sleep 5;
            basefs genkey;
            basefs get test ${docker_ip};
            #basefs resources test -l -r > /mnt/tmp/logs/node-$ix-resources &
            #tc qdisc add dev eth0 root handle 1:0 netem delay 100ms 20ms distribution normal reorder 25% 50% loss 20% 25%;
            #tc qdisc add dev eth0 parent 1:1 handle 10: tbf rate 10mbit buffer 75000 latency 5ms;
            mkdir -p /tmp/test;
            basefs mount test /tmp/test -d &> /mnt/tmp/logs/node-$ix'
    fi
    num=${2:-29}
    for ix in $(seq 1 $num); do
        evaluated=$(eval "echo \"${cmd}\"")
        echo "$ix $evaluated" >> /tmp/eval_status
        if [[ $ix -eq 1 ]]; then
            docker run -v $BASEFSPATH:/mnt --privileged --cap-add SYS_ADMIN --device /dev/fuse --name docker0 -t basefs /bin/bash -c "$evaluated" &
            sleep 1
        else
            docker run -v $BASEFSPATH:/mnt --privileged --cap-add SYS_ADMIN --device /dev/fuse --link docker0:docker0 -t basefs /bin/bash -c "$evaluated" &
        fi
    done
    mkdir -p /tmp/test;
    basefs mount test /tmp/test/ -iface docker0 -d 2>&1 | tee $BASEFSPATH/tmp/logs/node-0
}


function bstart () {
    dock $@
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
    grep " basefs.gossip: Sending " $BASEFSPATH/tmp/logs/node-0 | awk {'print $1 " " $2 " " $(NF-5) " " $(NF)'} | while read line; do
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
        grep -ha " basefs.gossip: Sending " $file | sed "s#\s*2016/01/.*2016-01-#2016-01-#" | awk {'print $1 " " $2 " " $(NF-5) " " $(NF)'} | while read line; do
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


function gpopulate () {
    basefs bootstrap test -i 127.0.0.1 -f
    mkdir /tmp/test
    basefs mount test /tmp/test -d > /dev/null 2> /tmp/testlog &
    sleep 4
    pid=$!
    ones=0
    twos=0
    fours=0
    sixteen=0
    rounds=( 1 1 1 1 1 1 1 1 1 1 1 1 1 5 6 6 7 7 8 7 7 7 16 20 15 10 16 20 16 20 1 1 1 1 1 1 1 1 24 20 20 32 30 )
    counter=0
    while true; do
        for i in ${rounds[@]}; do 
            cat /dev/urandom | fold -w 700 | head -n $i > /tmp/t;
            cp /tmp/t /tmp/test/gtestfile-1-$counter
            sleep 0.1
            messages=$(grep 'basefs.gossip: Sending [0-9]* block messages' /tmp/testlog | tail -n1 | sed -E "s/.*Sending ([0-9]+) block.*/\1/")
            echo "$i, $messages"
            e=true
            if [[ $ones -lt 160 ]]; then
                e=false
                if [[ $messages -eq 1 ]]; then
                    cp /tmp/t $BASEFSPATH/tmp/testpoint/testfile-1-$ones
                    ones=$(($ones+1))
                fi
            fi
            if [[ $twos -lt 40 ]]; then
                e=false
                if [[ $messages -eq 2 ]]; then
                    cp /tmp/t $BASEFSPATH/tmp/testpoint/testfile-2-$twos
                    twos=$(($twos+1))
                fi
            fi
            if [[ $fours -lt 20 ]]; then
                e=false
                if [[ $messages -eq 4 ]]; then
                    cp /tmp/t $BASEFSPATH/tmp/testpoint/testfile-4-$fours
                    fours=$(($fours+1))
                fi
            fi
            if [[ $sixteen -lt 20 ]]; then
                e=false
                if [[ $messages -eq 16 ]]; then
                    cp /tmp/t $BASEFSPATH/tmp/testpoint/testfile-16-$sixteen
                    sixteen=$(($sixteen+1))
                fi
            fi
            counter=$(($counter+1))
            if [[ $e == true ]]; then
                kill $pid
                exit
            fi
        done
        echo $ones $twos $fours $sixteen
    done
}


function populate () {
    basefs bootstrap test -i $CONFINEIP -f
    basefs mount test /tmp/test -d > /dev/null 2> /tmp/testlog &
    sleep 4
    pid=$!
    unset rounds
    unset iterations
    rounds=( 127 )
    #0 1 3 5 7 11 15 23 31 47 63 85 127 191 255)
    iterations=( 170 180 190 200 220 250 )
    counter=0
    loop=0
    entry=''
    while true; do
        for j in ${iterations[@]}; do
            cat /dev/urandom | fold -w 700 | head -n $(($j+$loop)) > /tmp/t;
            cp /tmp/t /tmp/test/testfile-$counter
            sleep 0.01
            current=$(grep 'basefs.gossip: Sending [0-9]* block messages' /tmp/testlog | tail -n1|awk {'print $11'})
            while [[ "$current" == "$entry" ]]; do
                current=$(grep 'basefs.gossip: Sending [0-9]* block messages' /tmp/testlog | tail -n1|awk {'print $11'})
                sleep 0.01
            done
            entry=$current
            echo $entry
            messages=$(grep 'basefs.gossip: Sending [0-9]* block messages' /tmp/testlog | tail -n1 | sed -E "s/.*Sending ([0-9]+) block.*/\1/")
            echo "$j, $messages"
            cp /tmp/t /tmp/t-$(($messages+1))
            if [[ " ${rounds[@]} " =~ " ${messages} " ]]; then
                cp /tmp/t $BASEFSPATH/tmp/testpoint/testfile-$(($messages+1))
                echo cp /tmp/t $BASEFSPATH/tmp/testpoint/testfile-$(($messages+1))
                for i in ${!rounds[@]} ; do
                    if [[ ${rounds[$i]} == $messages ]] ; then
                        unset rounds[$i]
                    fi
                done
                echo "MATCH, remaining ${#rounds[@]} ${rounds[@]}"
                if [[ ${#rounds[@]} -eq 0 ]]; then
                    killall basefs serf
                    return
                fi
            fi
            countes=$(($counter+1))
        done
        loop=$(($loop+1))
    done
}
