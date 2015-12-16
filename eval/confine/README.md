# BaseFS Community-Lab Evaluation


High-Performance experiment conductor design for [Confine](https://community-lab.net/) testbeds using concurrency and SSH control persist.



```bash
pip install requests
git clone https://github.com/glic3rinu/basefs.git
```

```bash
mkdir basefs/eval/confine/env
cd basefs/eval/confine/env
export PATH=$PATH:$(pwd)/../src/

# Collect all the slivers IP addresses
export SLICE_ID=2118
getips | tee ips.txt -

# Public interface selection
rm logs/ifconfig/*
run ifconfig pub0
grep -l 'inet addr' logs/ifconfig/*|cut -d'/' -f3|cut -d'.' -f1|xargs -i sed -n {}p ips.txt > good.ips.txt
mv good.ips.txt ips.txt

# Internet selection
rm logs/ping/*
run ping -c 1 -w 3 8.8.8.8
grep -l ' 0% packet loss,' logs/ping/*|cut -d'/' -f3|cut -d'.' -f1|xargs -i sed -n {}p ips.txt > good.ips.txt
mv good.ips.txt ips.txt


ping -c 1 -w 3 \$IP &> /dev/null && HOP=\$(traceroute -w 1 -n \$IP | tail -n1 | awk {'print \$1'} 2> /dev/null)


# Deploy the experiment on all the nodes
# `run` will run the provided script on the remote nodes, it also accept direct commands like: run ls
put ../src/deploy
run ../src/deploy
^C

# Run the experiment
ips=$(grep -h 'inet addr' logs/ifconfig/*|cut -d':' -f2|awk {'print $1'}|tr '\n' ',')
ssh glic3rinu@calmisko.org "basefs bootstrap test -i 10.228.207.204,${ips::-1} -f"
ssh glic3rinu@calmisko.org "basefs bootstrap test -i 10.228.207.204,10.159.1.124 -f"
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
