
bold=$(tput bold)
normal=$(tput sgr0)


function run () {
    # Accepts local script filename or command
    IP="$1"
    shift;
    CMD=$@
    echo "Going to run [$IP] $CMD" >&2
    ssh -o stricthostkeychecking=no \
        -o BatchMode=yes \
        -o EscapeChar=none \
        -o ControlMaster=auto \
        -o ControlPersist=yes \
        -o ControlPath=~/.ssh/confine-%r-%h-%p \
        root@$IP "$CMD" && echo "Success on $IP" || echo "Failure on $IP" >&2
}
export -f run



function put () {
    IP="$1"
    origin="$2"
    target="$3"
    echo "Going to copy $origin to root@[$IP]:${target}" >&2
    scp -o stricthostkeychecking=no \
        -o BatchMode=yes \
        -o EscapeChar=none \
        -o ControlMaster=auto \
        -o ControlPersist=yes \
        -o ControlPath=~/.ssh/confine-%r-%h-%p \
        -p $origin root@[$IP]:${target} && echo "Success on $IP" || echo "Failure on $IP" >&2
}
export -f put


function get () {
    IP="$1"
    origin="${@:2:$#-2}"
    target="${@: -1}"
    echo "Going to copy root@[$IP]:$origin $target" >&2
    scp -o stricthostkeychecking=no \
        -o BatchMode=yes \
        -o EscapeChar=none \
        -o ControlMaster=auto \
        -o ControlPersist=yes \
        -o ControlPath=~/.ssh/confine-%r-%h-%p \
        root@[$IP]:"$origin" "$target" && echo "Success on $IP" || echo "Failure on $IP" >&2
}
export -f get


function taillogs () {
    echo 
    echo
    while true; do
        sleep 0.5
        current=$(ps -o ppid,pid,comm|grep "ssh\|scp"|wc -l)
        if [[ $current -eq 0 ]]; then
            kill $$
            exit 0
        elif [[ $last -ne $current ]]; then
            echo "Remmaining: $current"
        fi
        last=$current
    done &
    tail -f $@
}
export -f taillogs
