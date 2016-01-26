# BaseFS Community-Lab Evaluation


High-Performance experiment conductor design for [Confine](https://community-lab.net/) testbeds using concurrency and SSH control persist.

resources: 600MB minimum, 700 MB optimal
        public ip address

```bash
pip install requests==2.6.0
git clone https://github.com/glic3rinu/basefs.git
```

```bash
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

# Collect all the slivers IP addresses
export SLICE_ID=2948
getips | tee ips.txt

# Public interface selection
rm logs/ifconfig/*
run ifconfig pub0
grep -l 'inet addr' logs/ifconfig/*|cut -d'/' -f3|cut -d'.' -f1|xargs -i sed -n {}p ips.txt | tee good.ips.txt
mv good.ips.txt ips.txt

# Internet selection
rm logs/ping/*
run ping -c 1 -w 4 8.8.8.8
grep -l ' 0% packet loss,' logs/ping/*|cut -d'/' -f3|cut -d'.' -f1|xargs -i sed -n {}p ips.txt | tee good.ips.txt
mv good.ips.txt ips.txt

# Characterize
. ./utils.sh
characterize

python traceroure.py results/$(ls -tr results | tail -n1)/*/traceroute



ping -c 1 -w 3 \$IP &> /dev/null && HOP=\$(traceroute -w 1 -n \$IP | tail -n1 | awk {'print \$1'} 2> /dev/null)


# Deploy the experiment on all the nodes
# `run` will run the provided script on the remote nodes, it also accept direct commands like: run ls
put ../src/deploy
run ../src/deploy
^C

# Run the experiment
ips=$(grep -h 'inet addr' logs/ifconfig/*|cut -d':' -f2|awk {'print $1'}|tr '\n' ',')
ssh glic3rinu@calmisko.org "basefs bootstrap test -i $CONFINEIP,${ips::-1} -f"
ssh glic3rinu@calmisko.org "basefs bootstrap test -i $CONFINEIP,10.159.1.124 -f"
ssh root@calmisko.org
openntpd -f /etc/ntpd.conf
su - glic3rinu
mkdir -p /tmp/{test,logs}
basefs mount test /tmp/test/ -iface tap0 -d 2>&1 | tee /tmp/output -



run basefs get test 147.83.168.171 -f
run mkdir /tmp/test
run basefs run test /tmp/test -d &> /tmp/results &

watch -n 1 tail -n 40 /tmp/results

run ../src/experiment



# Characterize latency and hops



^C

# Collect the results once the experiment is finished
# Results will be stored in env/results/date/
get test.pcap
^C

```
