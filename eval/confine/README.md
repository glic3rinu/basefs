# BaseFS Community-Lab Evaluation


High-Performance experiment conductor design for [Confine](https://community-lab.net/) testbeds using concurrency and SSH control persist.

resources: 600MB minimum, 700 MB optimal
        public ip address

```bash
pip install requests==2.6.0
git clone https://github.com/glic3rinu/basefs.git
```

```bash
. ../env.sh
cd $BASEFSPATH/eval/confine
# Collect all the slivers IP addresses
getips | tee ips.txt

# Public interface selection
rm logs/ifconfig/*
run ifconfig pub0
grep -l 'inet addr' logs/ifconfig/*|cut -d'/' -f3|cut -d'.' -f1|xargs -i sed -n {}p ips.txt | tee good.ips.txt
mv good.ips.txt ips.txt

# Internet selection
rm logs/ping/*
run ping -c 1 -w 4 $CONFINEIP
grep -l ' 0% packet loss,' logs/ping/*|cut -d'/' -f3|cut -d'.' -f1|xargs -i sed -n {}p ips.txt | tee good.ips.txt
mv good.ips.txt ips.txt

# Characterize
. ./utils.sh
characterize

python traceroure.py results/$(find results/|grep trace|sort -n|tail -n1|cut -d'/' -f2)/*/traceroute


ping -c 1 -w 3 \$IP &> /dev/null && HOP=\$(traceroute -w 1 -n \$IP | tail -n1 | awk {'print \$1'} 2> /dev/null)


# Deploy the experiment on all the nodes
# `run` will run the provided script on the remote nodes, it also accept direct commands like: run ls
put ../src/deploy
run ../src/deploy
^C

# Run the experiment
### start
bash conv.sh
### stop
run bash experiment -s
### collect
run bash experiment -c
get /tmp/{results,resources}
rpath="results/$(ls -tr results/ | tail -n1)"
rm -fr $BASEFSPATH/tmp/confine-conv/logs-1
mkdir -p $BASEFSPATH/tmp/confine-conv/logs-1
for num in $(ls "$rpath"); do
    mv "$rpath/$num/results" $BASEFSPATH/tmp/confine-conv/logs-1/node-$num
    mv "$rpath/$num/resources" $BASEFSPATH/tmp/confine-conv/logs-1/node-$num-resources
done
cp $BASEFSPATH/tmp/logs/node-0* $BASEFSPATH/tmp/confine-conv/logs-1/


cd ../../tmp/
readscenarios confine > /tmp/confine.csv




# Characterize latency and hops


^C

# Collect the results once the experiment is finished
# Results will be stored in env/results/date/
get test.pcap
^C

```
