
```bash
rsync -avhP --exclude=datasets --exclude=tmp --exclude=.git --exclude=env --exclude="*~" --exclude=logs --exclude=results --exclude=__pycache__ /home/glic3/Dropbox/basefs root@calmisko.org:

rsync -avhP --exclude=__pycache__ root@calmisko.org:basefs/eval/datasets/ /home/glic3/Dropbox/basefs/eval/datasets/
```


```bash
if [[ -e /home/glic3/Dropbox/basefs/ ]]; then
    export BASEFSPATH=/home/glic3/Dropbox/basefs/
else
    export BASEFSPATH=/root/basefs/
fi

. $BASEFSPATH/eval/plots/read.sh
cd $BASEFSPATH/tmp

# BaseFS convergence
readscenarios basefseval > $BASEFSPATH/eval/datasets/basefs.csv 2> $BASEFSPATH/eval/basefs-completed.csv
bash $BASEFSPATH/eval/plots/basefs.sh
eog $BASEFSPATH/eval/plots/basefseval.png

# Gossip convergence
readscenarios gossip > $BASEFSPATH/eval/datasets/gossip.csv 2> $BASEFSPATH/eval/datasets/gossip-completed.csv
readscenarios basefs > $BASEFSPATH/eval/datasets/basefs-loss.csv 2> $BASEFSPATH/eval/datasets/basefs-loss-completed.csv
bash $BASEFSPATH/eval/plots/conv.sh

# Sync Convergence
readscenarios sync > $BASEFSPATH/eval/datasets/sync.csv
readtotaltraffic sync > $BASEFSPATH/eval/datasets/sync-traffic.csv
bash $BASEFSPATH/eval/plots/sync.sh


# Perfomance
readperformance > $BASEFSPATH/eval/datasets/performance.csv
bash $BASEFSPATH/eval/plots/performance.sh
```
