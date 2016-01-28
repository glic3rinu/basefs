#!/bin/bash


# readscenarios gossip > /tmp/scenarios.csv 2> /tmp/completed.csv
# scp root@calmisko.org:/tmp/*csv /tmp/
# cp /tmp/scenarios.csv /tmp/scenarios.csv.w; cp /tmp/completed.csv /tmp/completed.csv.w
# grep "loss\|scenario\|reference" /tmp/scenarios.csv.w > /tmp/scenarios.csv ; bash ./gossipconv.sh; eog gossipconv.png
# grep "loss\|scenario\|reference" /tmp/completed.csv.w > /tmp/completed.csv ; bash ./gossipconv.sh completed; eog gossipconv-completed.png



function graphscenarios () {
    cat << 'EOF' | Rscript --vanilla - $BASEFSPATH
    library(ggplot2)
    library(ggthemes)
    library(Hmisc)
    args <- commandArgs(trailingOnly = TRUE)

    do_graphs <- function (dataset, dataset_completed, var, name) {
        current <- dataset[grepl(var, dataset$scenario) | dataset$scenario=="baseline",]
        ggplot(data=current, aes(x=messages+1, y=time, color=factor(scenario))) +
          geom_point(alpha=0.5) +
          stat_summary(fun.data = "mean_cl_boot", size=1, alpha=0.5) +
          scale_x_log10()
        ggsave(paste0(args[1], "/eval/plots/", name, "-", var, ".png"), dpi=600)
        
        current <- dataset_completed[grepl(var,dataset_completed$scenario) | dataset_completed$scenario=="baseline",]
        ggplot(data=current, aes(x=messages+1, y=completed, color=factor(scenario))) +
            geom_line() +
            geom_point() +
            scale_x_log10()
        ggsave(paste0(args[1], "/eval/plots/", name, "-", var, "-completed.png"), dpi=600)
        print(paste0("eog ", args[1], "/eval/plots/", name, "-", var, "-completed.png"))
    }
    
    gossip = read.csv(paste0(args[1], "/eval/datasets/gossip.csv"))
    gossip_completed = read.csv(paste0(args[1], "/eval/datasets/gossip-completed.csv"))
    
    for (var in c("loss", "bw", "delay", "reorder")) {
        do_graphs(gossip, gossip_completed, var, 'gossip')
    }
    
    basefs_loss = read.csv(paste0(args[1], "/eval/datasets/basefs-loss.csv"))
    basefs_loss_completed = read.csv(paste0(args[1], "/eval/datasets/basefs-loss-completed.csv"))
    do_graphs(basefs_loss, basefs_loss_completed, 'loss', 'basefs')
    
#    ggplot(data=scenarios, aes(x=messages+1, y=time)) +
#      geom_point(alpha=0.1) + 
#      stat_summary(fun.data = "mean_cl_boot", size=2, alpha=0.5) + 
#      facet_grid(~scenario) +
#      scale_x_log10()
#    ggsave("gossipconv2.png", dpi=600)
EOF
}

graphscenarios
