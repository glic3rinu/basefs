#!/bin/bash


DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"


function stop () {
#    ssh root@calmisko.org { killall serf; killall /usr/bin/python3; killall bash; } &
    run killall serf &
    run killall /usr/bin/python3 &
    run killall bash
}


function sshc () {
    CMD=$@
    echo "Going to run glic3rinu@calmisko.org $CMD" >&2
    ssh -o stricthostkeychecking=no \
        -o BatchMode=yes \
        -o EscapeChar=none \
        -o ControlMaster=auto \
        -o ControlPersist=yes \
        -o ControlPath=~/.ssh/confine-%r-%h-%p \
        glic3rinu@calmisko.org "$@"
}

function scpc () {
    origin="${@:1:$#-1}"
    target="${@: -1}"
    echo "Going to copy glic3rinu@calmisko.org:$origin $target" >&2
    scp -o stricthostkeychecking=no \
        -o BatchMode=yes \
        -o EscapeChar=none \
        -o ControlMaster=auto \
        -o ControlPersist=yes \
        -o ControlPath=~/.ssh/confine-%r-%h-%p \
        glic3rinu@calmisko.org:"$origin" "$target"
}


function pipinstall {
    run pip3 install basefs==1-dev --allow-external basefs --allow-unverified basefs
}


function bootstrap {
    ips=$(grep -h 'inet addr' logs/ifconfig/*|cut -d':' -f2|awk {'print $1'}|tr '\n' ',')
    cat << EOF | sshc
        basefs bootstrap test -i 10.228.207.204,${ips::-1} -f
        mkdir -p /tmp/{test,logs}
EOF
}

# basefs mount test /tmp/test/ -iface tap0 -d 2>&1 | tee /tmp/output

function cwrite {
    size=${1:-1}
    if [[ size -eq 1 ]]; then
        fold=10;
    else
        fold=470;
    fi
    sshc "cat /dev/urandom | fold -w $fold | head -n $size > /tmp/test/testfile"
}

function collect {
    run bash experiment -c
    results_dir="$DIR/results/$(date +%Y.%m.%d-%H:%M:%S)"
    get /tmp/{results,traffic}
    mkdir $results_dir/0
    sshc $(cat << 'EOF'
        grep -ah "Sending entry " /tmp/output | while read line;
            do echo $(date '+%s.%3N' -d "$(echo $line | awk {'print $1 " " $2'})") $(echo $line| awk {'print $7'});
        done > /tmp/results
EOF
    )
    scpc /tmp/{results,traffic} $results_dir/0/
}


function characterize () {
    cmd=$(cat << EOF
        ips=( 10.228.207.204 $(grep -h 'inet addr' logs/ifconfig/*|cut -d':' -f2|awk {'print $1'}|tr '\n' ' ') );
        self=\$({ ip -f inet -o addr show pub0 || ip -f inet -o addr show tap0; }|awk {'print \$4'}|cut -d'/' -f1);
        echo -n '' > /tmp/traceroute;
        for ip in \${ips[@]}; do
            if [[ \$self != \$ip ]]; then
                latency=\$(ping -c 1 -w 2 \$ip);
                if [[ \$? -eq 0 ]]; then
                    avg_latency=\$(echo "\$latency" | tail -n 1 | cut -d'/' -f5);
                    hops=\$(traceroute -w 1 -n \$ip | awk {'print \$2'} | grep -v 'to' | tr '\n' ' ');
                    echo \$self \$ip \$avg_latency \$hops >> /tmp/traceroute;
                fi;
            fi;
        done
EOF
    )
    run $cmd
    sshc $cmd
    results_dir="results/$(date +%Y.%m.%d-%H:%M:%S)"
    get /tmp/traceroute
    mkdir $DIR/$results_dir/0
    scpc /tmp/traceroute $results_dir/0/traceroute
}


function experiment1 () {
    {
        sleep 2;
        run bash experiment -r
    } &
    sshc $(cat << 'EOF'
    if [[ $(whoami) == 'root' ]]; then
        iptables -D OUTPUT -p udp --sport 18374 -j LOG;
        iptables -D OUTPUT -p tcp --sport 18374 -j LOG;
        iptables -D OUTPUT -p tcp --sport 18376 -j LOG;
    
        iptables -A OUTPUT -p udp --sport 18374 -j LOG;
        iptables -A OUTPUT -p tcp --sport 18374 -j LOG;
        iptables -A OUTPUT -p tcp --sport 18376 -j LOG;
        {
            echo -n '' > /tmp/traffic;
            while true; do
                result="";
                while read line; do;
                    result="${result}$line ";
                done < <(iptables -n -L -v | grep "LOG .* spt:" | awk {'split($11, port, ":"); print $10":"port[2]":"$1":"$2'});
                echo $(date '+%s' -d "+ $offset seconds") "$result" >> /tmp/traffic;
                sleep 1;
            done;
        } &

        pid=$!;
        trap "kill $pid; echo aaaaaaa" INT;
        su - glic3rinu bash -c '
            basefs bootstrap test -i 10.228.207.204,10.159.1.124 -f;
            mkdir -p /tmp/test;
            echo '' > /tmp/output
            basefs mount test /tmp/test/ -iface tap0 -d 2>&1 | tee /tmp/output;';
    fi;
EOF
)
}

