#!/bin/bash

# BECAUSE NOT ALL CONFINE NODES HAVE INTERNET, AND THERE ARE VERY FEW NODES AVAILABLE
# INSTALLS BASEFS ON A "TEMPLATE" NODE AND THEN REPLICATE ALL THE CHANGES TO THE REST


export TEMPLATEIP="fdf5:5351:1dfd:8c:1001::d58"

ssh root@$TEMPLATEIP 'sed -i "s/wheezy/jessie/" /etc/apt/sources.list
    apt-get update'

rsync -avhP --delete "root@[$TEMPLATEIP]":/var/cache/apt/ packages/

cat << 'EOF' > install.sh
ssh root@$TEMPLATEIP
#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
apt-get install -y --force-yes locales
sed -i "s/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/" /etc/locale.gen
locale-gen
apt-get install -y \
    libfuse2 \
    python3-pip \
    netcat-openbsd \
    ntpdate
pip3 install https://github.com/glic3rinu/basefs/tarball/master#egg=basefs-dev
EOF
chmod +x install.sh
rsync -avhP install.sh "root@[$TEMPLATEIP]":/tmp/
ssh root@$TEMPLATEIP /tmp/install.sh


rsync -avhP --delete "root@[$TEMPLATEIP]":/usr/local/lib/python3.4/dist-packages/ python/
rsync -avhP --delete "root@[$TEMPLATEIP]":/usr/local/bin/serf serf
rsync -avhP --delete "root@[$TEMPLATEIP]":/usr/local/bin/basefs basefs


# From bestia to every node
cat << 'EOF' > install.sh
#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
sed -i "s/wheezy/jessie/" /etc/apt/sources.list
sed -i "s/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/" /etc/locale.gen
apt-get install -y --force-yes locales
locale-gen
apt-get install -y \
    libfuse2 \
    python3-pip \
    netcat-openbsd \
    ntpdate
apt-get clean
apt-get -y remove build-essential
apt-get -y autoremove
EOF

chmod +x install.sh
cat ips.txt | while read ip; do
    if [[ "$ip" != "$TEMPLATEIP" ]]; then
        {
            rsync -avhP packages/ "root@[$ip]":/var/cache/apt/
            rsync -avhP apt/ "root@[$ip]":/var/lib/apt/
            rsync -avhP install.sh "root@[$ip]":/tmp/
            ssh root@$ip /tmp/install.sh 
            rsync -avhP python/ "root@[$ip]":/usr/local/lib/python3.4/dist-packages/
            rsync -avhP serf "root@[$ip]":/usr/local/bin/serf
            rsync -avhP basefs "root@[$ip]":/usr/local/bin/basefs
        } &> /tmp/$ip.log &
    fi
done


# ssh on every node
