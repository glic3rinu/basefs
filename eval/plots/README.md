
```bash
rsync -avhP --exclude=datasets --exclude=tmp --exclude=.git --exclude=env --exclude="*~" --exclude=logs --exclude=results --exclude=__pycache__ /home/glic3/Dropbox/basefs root@calmisko.org:
rsync -avhP --exclude=datasets --exclude=tmp --exclude=.git --exclude=env --exclude="*~" --exclude=logs --exclude=results --exclude=__pycache__ /home/glic3rinu/Dropbox/basefs /root

rsync -avhP --exclude=__pycache__ root@calmisko.org:basefs/eval/datasets/ /home/glic3/Dropbox/basefs/eval/datasets/
rsync -avhP --exclude=__pycache__ /root/basefs/eval/datasets/ /home/glic3rinu/Dropbox/basefs/eval/datasets/
```


```bash
. ../env.sh
cd $BASEFSPATH/tmp

# Gossip Layer
readscenarios gossip > $BASEFSPATH/eval/datasets/gossip.csv 2> $BASEFSPATH/eval/datasets/gossip-completed.csv
readscenarios basefs > $BASEFSPATH/eval/datasets/basefs-loss.csv 2> $BASEFSPATH/eval/datasets/basefs-loss-completed.csv
$BASEFSPATH/eval/plots/conv.R

# Sync Protocol
readscenarios sync > $BASEFSPATH/eval/datasets/sync.csv
readtotaltraffic sync > $BASEFSPATH/eval/datasets/sync-traffic.csv
$BASEFSPATH/eval/plots/sync.R

# Confine Characterization
$BASEFSPATH/eval/plots/confine_characterization.py

# BaseFS convergence docker/confine
readscenarios basefsdocker > $BASEFSPATH/eval/datasets/basefs-docker.csv
readscenarios basefsconfine > $BASEFSPATH/eval/datasets/basefs-confine.csv
$BASEFSPATH/eval/plots/basefs.R

# Traffic usage/balance
readtraffic basefsdocker/*/*-resources > $BASEFSPATH/eval/datasets/basefs-docker-traffic.csv 2> $BASEFSPATH/eval/datasets/basefs-docker-traffic-distribution.csv
readtraffic basefsconfine/*/*-resources > $BASEFSPATH/eval/datasets/basefs-confine-traffic.csv 2> $BASEFSPATH/eval/datasets/basefs-confine-traffic-distribution.csv
$BASEFSPATH/eval/plots/traffic.R

# Perfomance
readperformance > $BASEFSPATH/eval/datasets/performance.csv
$BASEFSPATH/eval/plots/performance.R

```
