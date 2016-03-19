
```bash
rsync -rvhP --exclude="*.png" --exclude=datasets --exclude=tmp --exclude=.git --exclude=env --exclude="*~" --exclude=logs --exclude=results --exclude=__pycache__ /home/glic3/Dropbox/basefs root@calmisko.org:
rsync -rvhP --exclude="*.png" --exclude=datasets --exclude=tmp --exclude=.git --exclude=env --exclude="*~" --exclude=logs --exclude=results --exclude=__pycache__ /home/glic3rinu/Dropbox/basefs /root
rsync -rvhP --exclude=datasets --exclude=tmp --exclude=.git --exclude=env --exclude="*~" --exclude=logs --exclude=results --exclude=__pycache__ /home/glic3/Dropbox/basefs /root
rsync -rvhp root@calmisko.org:/root/basefs/tmp/testpoint /root/basefs/tmp/testpoint 


rsync -rvhP --exclude=__pycache__ root@calmisko.org:basefs/eval/datasets/basefs* /home/glic3/Dropbox/basefs/eval/datasets/
rsync -rvhP --exclude=__pycache__ /root/basefs/eval/datasets/basefs* /home/glic3rinu/Dropbox/basefs/eval/datasets/
rsync -rvhP --exclude=__pycache__ root@xps:/root/basefs/eval/datasets/basefs* /home/glic3rinu/Dropbox/basefs/eval/datasets/

```


```bash
. ../env.sh
cd $BASEFSPATH/tmp

# Gossip Layer
readscenarios gossip > $BASEFSPATH/eval/datasets/gossip.csv 2> $BASEFSPATH/eval/datasets/gossip-completed.csv
readscenarios basefs > $BASEFSPATH/eval/datasets/basefs.csv 2> $BASEFSPATH/eval/datasets/basefs-completed.csv
$BASEFSPATH/eval/plots/conv.R

# Sync Protocol
readscenarios sync > $BASEFSPATH/eval/datasets/sync.csv
readtotaltraffic sync > $BASEFSPATH/eval/datasets/sync-traffic.csv
$BASEFSPATH/eval/plots/sync.R

# Scalability
readscenarios scalability > $BASEFSPATH/eval/datasets/scalability.csv 2> $BASEFSPATH/eval/datasets/scalability-completed.csv
readload > $BASEFSPATH/eval/datasets/scalability-load.csv
<!--readoverhead > $BASEFSPATH/eval/datasets/scalability-overhead.csv-->
$BASEFSPATH/eval/plots/scalability.R

# Confine Characterization
$BASEFSPATH/eval/plots/confine_characterization.py 2> $BASEFSPATH/eval/datasets/characterization.csv

# BaseFS convergence docker/confine
readscenarios basefsdocker > $BASEFSPATH/eval/datasets/basefs-docker.csv
readscenarios basefsconfine > $BASEFSPATH/eval/datasets/basefs-confine.csv
readtraffic basefsdocker/*/*-resources > $BASEFSPATH/eval/datasets/basefs-docker-traffic.csv 2> $BASEFSPATH/eval/datasets/basefs-docker-traffic-distribution.csv
readtraffic basefsconfine/*/*-resources > $BASEFSPATH/eval/datasets/basefs-confine-traffic.csv 2> $BASEFSPATH/eval/datasets/basefs-confine-traffic-distribution.csv
$BASEFSPATH/eval/plots/basefs.R


# Perfomance
readperformance > $BASEFSPATH/eval/datasets/performance.csv
$BASEFSPATH/eval/plots/performance.R

$BASEFSPATH/eval/plots/performance2.R

# /etc
$BASEFSPATH/eval/etc_characerization.py > $BASEFSPATH/eval/datasets/etc.csv
$BASEFSPATH/eval/plots/etc.R

```
