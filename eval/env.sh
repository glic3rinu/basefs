#!/bin/bash


if [[ -e /home/glic3/Dropbox/basefs/ ]]; then
    export BASEFSPATH=/home/glic3/Dropbox/basefs/
    export CONFINEIP=$(ssh root@calmisko.org ifconfig tap0 | grep "inet addr:"|awk {'print $2'}|cut -d':' -f2)
else
    if [[ $(whoami) == "root" ]]; then
        export BASEFSPATH=/root/basefs/
    else
        export BASEFSPATH=/home/glic3rinu/Dropbox/basefs/
    fi
    export CONFINEIP=$(ip addr|grep tap0|grep inet|sed -E "s#.* inet ([^/]+)/.*#\1#")
fi
export PYTHONPATH=$BASEFSPATH
export PATH=$PATH:$(realpath $BASEFSPATH/eval/confine/src)
[[ "$CONFINEIP" == "" ]] && echo "CONFINEIP not set"

export SLICE_ID=2948

. $BASEFSPATH/eval/plots/read.sh
