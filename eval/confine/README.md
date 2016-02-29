# BaseFS Community-Lab Evaluation


High-Performance experiment conductor design for [Confine](https://community-lab.net/) testbeds using concurrency and SSH control persist.

resources: 600MB minimum, 700 MB optimal
public ip address



```bash
pip3 install requests==2.6.0
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
run ping -c 1 -w 10 $CONFINEIP
grep -l ' 0% packet loss,' logs/ping/*|cut -d'/' -f3|cut -d'.' -f1|xargs -i sed -n {}p ips.txt | tee good.ips.txt
cp good.ips.txt ips.txt

# Prepare dataset
gpopulate


# Deploy
# APT and PIP proxies in order to install BaseFS required dependencies in all slivers.
apt-get install apt-cacher-ng

export TEMPLATEIP="fdf5:5351:1dfd:66:1001::d5e"
# WARNING MAKE SURE TO UPDATE APT PROXY IP
cat << 'EOF' > install.sh
#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
sed -i "s/wheezy/jessie/" /etc/apt/sources.list
ping -c1 -w1 8.8.8.8 || {
    echo 'Acquire::http { Proxy "http://10.228.207.205:3142"; };' > /etc/apt/apt.conf.d/02proxy
}
apt-get update
apt-get install -y --force-yes locales
sed -i "s/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/" /etc/locale.gen
locale-gen
apt-get install -y \
    libfuse2 \
    python3-pip \
    netcat-openbsd \
    ntpdate
if [[ $1 == "TEMPLATE" ]]; then
    pip3 install https://github.com/glic3rinu/basefs/tarball/master#egg=basefs-dev
fi
apt-get clean
apt-get -y remove build-essential
apt-get -y autoremove
EOF
chmod +x install.sh
rsync -avhP install.sh "root@[$TEMPLATEIP]":/tmp/
ssh root@$TEMPLATEIP /tmp/install.sh TEMPLATE

rsync -avhP --delete "root@[$TEMPLATEIP]":/usr/local/lib/python3.4/dist-packages/ python/
rsync -avhP "root@[$TEMPLATEIP]":/usr/local/bin/serf serf
rsync -avhP "root@[$TEMPLATEIP]":/usr/local/bin/basefs basefs

ssh root@$TEMPLATEIP basefs

# From bestia to every node
cat ips.txt | while read ip; do
    if [[ "$ip" != "$TEMPLATEIP" ]]; then
        {
            rsync -avhP install.sh "root@[$ip]":/tmp/
            ssh root@$ip /tmp/install.sh
            rsync -avhP python/ "root@[$ip]":/usr/local/lib/python3.4/dist-packages/
            rsync -avhP serf "root@[$ip]":/usr/local/bin/serf
            rsync -avhP basefs "root@[$ip]":/usr/local/bin/basefs
        } &> /tmp/$ip.log &
    fi
done
tail -f /tmp/*.log
run basefs


# Test dataset locally
bash ../docker/experiments 4
readscenarios basefsdocker > $BASEFSPATH/eval/datasets/basefs-docker.csv
$BASEFSPATH/eval/plots/basefs.R


# Run the experiment
### deploy
put experiment
### Characterize
. ./utils.sh
characterize
rm -r ../datasets/confine-traceroute/*
cp -r results/$(ls -tr results/ | tail -n1)/* ../datasets/confine-traceroute/
### start
# Change every 6 seconds with a 10 seconds pause between repetitions
bash conv.sh
### stop
# run bash experiment -s
### collect
run bash experiment -c
get /tmp/{results,resources}
rpath="results/$(ls -tr results/ | tail -n1)"
rm -fr $BASEFSPATH/tmp/basefsconfine/logs-1
mkdir -p $BASEFSPATH/tmp/basefsconfine/logs-1
for num in $(ls "$rpath"); do
    mv "$rpath/$num/results" $BASEFSPATH/tmp/basefsconfine/logs-1/node-$num
    mv "$rpath/$num/resources" $BASEFSPATH/tmp/basefsconfine/logs-1/node-$num-resources
done
cp $BASEFSPATH/tmp/logs/node-0* $BASEFSPATH/tmp/basefsconfine/logs-1/


cd ../../tmp/
readscenarios basefsconfine > $BASEFSPATH/eval/datasets/basefs-confine.csv
rsync -avhP --exclude=__pycache__ root@calmisko.org:basefs/eval/datasets/basefs-confine.csv /home/glic3/Dropbox/basefs/eval/datasets/
$BASEFSPATH/eval/plots/basefs.R


# Perform same experiment locally, adjusting the number of nodes
bash ../docker/experiments 4 35
readscenarios basefsdocker > $BASEFSPATH/eval/datasets/basefs-docker.csv
$BASEFSPATH/eval/plots/basefs.R
```

