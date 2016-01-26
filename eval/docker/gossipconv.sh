#!/bin/bash


# readscenarios gossip > /tmp/scenarios.csv 2> /tmp/completed.csv
# scp root@calmisko.org:/tmp/*csv /tmp/
# cp /tmp/scenarios.csv /tmp/scenarios.csv.w; cp /tmp/completed.csv /tmp/completed.csv.w
# grep "loss\|scenario\|reference" /tmp/scenarios.csv.w > /tmp/scenarios.csv ; bash ./gossipconv.sh; eog gossipconv.png
# grep "loss\|scenario\|reference" /tmp/completed.csv.w > /tmp/completed.csv ; bash ./gossipconv.sh completed; eog gossipconv-completed.png


function graphscenarios () {
    cat << 'EOF' | Rscript -
    library(ggplot2)
    library(ggthemes)
    library(Hmisc)

    scenarios = read.csv("/tmp/scenarios.csv")
    ggplot(data=scenarios, aes(x=messages+1, y=time, color=factor(scenario))) +
      geom_point(alpha=0.5) +
      stat_summary(fun.data = "mean_cl_boot", size=1, alpha=0.5) +
      scale_x_log10()
    ggsave("gossipconv.png", dpi=600)

#    ggplot(data=scenarios, aes(x=messages+1, y=time)) +
#      geom_point(alpha=0.1) + 
#      stat_summary(fun.data = "mean_cl_boot", size=2, alpha=0.5) + 
#      facet_grid(~scenario) +
#      scale_x_log10()
#    ggsave("gossipconv2.png", dpi=600)
EOF
}


function graphcompleted () {
    cat << 'EOF' | Rscript -
    library(ggplot2)
    library(ggthemes)
    library(Hmisc)

    scenarios = read.csv("/tmp/completed.csv")
    ggplot(data=scenarios, aes(x=messages+1, y=completed, color=factor(scenario))) +
        geom_line() +
        geom_point() +
        scale_x_log10()
    ggsave("gossipconv-completed.png", dpi=600)
EOF
}


if [[ $1 != "" ]]; then
    graphcompleted
else
    graphscenarios
fi
