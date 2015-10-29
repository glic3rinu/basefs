Steps
=====

For creating a basefs 4-node test cluster with Docker

```bash
git clone https://github.com/glic3rinu/basefs.git

cd basefs
docker build -t serf .

BASEFS_PATH=$(pwd)/basefs

sudo ln -s $BASEFS_PATH/BIN/basefs /usr/local/bin/

mkdir -p $BASEFS_PATH/tmp/{keys,logs,fs}
basefs genkey $BASEFS_PATH/tmp/keys/root
basefs genkey $BASEFS_PATH/tmp/keys/serf0
basefs genkey $BASEFS_PATH/tmp/keys/serf1
basefs genkey $BASEFS_PATH/tmp/keys/serf2

basefs bootstrap -k $BASEFS_PATH/tmp/keys/root -i 172.17.42.1 $BASEFS_PATH/tmp/logs/root -f
cp $BASEFS_PATH/tmp/logs/root $BASEFS_PATH/tmp/logs/serf0
cp $BASEFS_PATH/tmp/logs/root $BASEFS_PATH/tmp/logs/serf1
cp $BASEFS_PATH/tmp/logs/root $BASEFS_PATH/tmp/logs/serf2

basefs mount -d -k $BASEFS_PATH/tmp/keys/root $BASEFS_PATH/tmp/logs/root $BASEFS_PATH/tmp/fs

DOCKER_ARGS="-v $BASEFS_PATH/tmp:/mnt --privileged --cap-add SYS_ADMIN --device /dev/fuse -i -t serf"
docker create --name serf0 $DOCKER_ARGS mnt/bin/basefs mount -d -k mnt/keys/serf0 mnt/logs/serf0 mnt/fs/serf0
docker create --name serf1 $DOCKER_ARGS --link serf0:serf0 mnt/bin/basefs mount -d -k mnt/keys/serf1 mnt/logs/serf1 mnt/fs/serf1
docker create --name serf2 $DOCKER_ARGS --link serf0:serf0 mnt/bin/basefs mount -d -k mnt/keys/serf2 mnt/logs/serf2 mnt/fs/serf2

docker start --name serf0
docker start --name serf1
docker start --name serf2

#docker exec serf1 usr/bin/serf join $(docker exec serf0 ifconfig|grep 172.17|sed -E 's/.*addr:([^ ]+).*/\1/')
#docker exec serf2 usr/bin/serf join $(docker exec serf0 ifconfig|grep 172.17|sed -E 's/.*addr:([^ ]+).*/\1/')

docker exec serf1 usr/bin/serf members
docker exec serf1 usr/bin/serf query hola

```
