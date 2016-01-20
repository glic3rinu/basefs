#!/bin/bash


. $(dirname "${BASH_SOURCE[0]}")/utils.sh


function readscenarios () {
    echo "scenario,size,node,time,completed"
    name=${1:-"scenario"}
    for scenario in $(ls -d ${name}-*); do
        scenario_name=$(echo "$scenario" | sed "s/$name-//")
        for log in $(ls  -d $BASEFSPATH/tmp/$scenario/logs-*); do
            grep " basefs.gossip: Sending " $log/node-0 | sed -E "s#([^:]+)\s*2016/01/.*2016-01-#\12016-01-#" | awk {'print $1 " " $2 " " $(NF-5) " " $(NF)'} | while read line; do
                line=( $line )
                start=$(date -d "${line[0]} ${line[1]} $(date '+%Z')" +'%s.%3N' || echo "$line" >&2)
                completed=1
                while read nodeline; do
                    linedate="$(echo $nodeline | cut -d':' -f2 | awk {'print $1'}) $(echo $nodeline | awk {'print $2'})"
                    node=$(echo "$nodeline" | cut -d':' -f1)
                    node=${node##*/}
                    echo $scenario_name,${line[2]},$node,$(echo $(date -d "$linedate UTC" +'%s.%3N' || echo "$nodeline ${line[3]}" >&2)-$start | bc | awk '{printf "%f\n", $0}'),$completed
                    completed=$(($completed+1))
                done < <(grep -a "COMPLETED ${line[3]}" $log/node-* | sed -E "s#([^:]+)\s*2016/01/.*2016-01-#\12016-01-#"| sed "s/:.*2016-01/:2016-01/" | awk {'print $1 " " $2'})
                if [[ $completed -lt 30 ]]; then
                    echo "[WARNING] Incomlete $scenario_name ${line[2]} $completed completed" >&2
                fi
            done
        done
    done
}


# readscenarios gossip > /tmp/scenarios.csv
# scp root@calmisko.org:/tmp/*csv /tmp/
# cp /tmp/scenarios.csv /tmp/scenarios.csv.w
# grep "scenario\|reorder\|reference" /tmp/scenarios.csv.w > /tmp/scenarios.csv


cat << 'EOF' | Rscript -
library(ggplot2)
library(ggthemes)
library(Hmisc)

scenarios = read.csv("/tmp/scenarios.csv")
ggplot(data=scenarios, aes(x=size+1, y=time, color=factor(scenario)))+
  geom_point(alpha=0.1) + stat_summary(fun.data = "mean_cl_boot", size=2, alpha=0.5) +
  scale_x_log10()

ggsave("gossipconv.png", dpi=600)

ggplot(data=scenarios, aes(x=size+1, y=time)) +
  geom_point(alpha=0.1) + 
  stat_summary(fun.data = "mean_cl_boot", size=2, alpha=0.5) + 
  facet_grid(~scenario) +
  scale_x_log10()
ggsave("gossipconv2.png", dpi=600)
EOF

