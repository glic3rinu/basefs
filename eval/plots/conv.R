#!/usr/bin/Rscript


library(ggplot2)
library(ggthemes)
library(Hmisc)
basefspath = Sys.getenv("BASEFSPATH")

do_graphs <- function (dataset, dataset_completed, var, name) {
    current <- dataset[grepl(var, dataset$scenario) | dataset$scenario=="baseline",]
    ggplot(data=current, aes(x=messages+1, y=time, color=factor(scenario))) +
      geom_point(alpha=0.5) +
      stat_summary(fun.data="mean_cl_boot", size=1, alpha=0.5) +
      scale_x_log10()
    
    ggsave(paste0(basefspath, "/eval/plots/", name, "-", var, ".png"), dpi=600)
    print(paste0("eog ", basefspath, "/eval/plots/", name, "-", var, ".png"))
    
    current <- dataset_completed[grepl(var,dataset_completed$scenario) | dataset_completed$scenario=="baseline",]
    ggplot(data=current, aes(x=messages+1, y=completed, color=factor(scenario))) +
        geom_line() +
        geom_point() +
        scale_x_log10()
    
    ggsave(paste0(basefspath, "/eval/plots/", name, "-", var, "-completed.png"), dpi=600)
    print(paste0("eog ", basefspath, "/eval/plots/", name, "-", var, "-completed.png"))
}

gossip = read.csv(paste0(basefspath, "/eval/datasets/gossip.csv"))
gossip_completed = read.csv(paste0(basefspath, "/eval/datasets/gossip-completed.csv"))

basefs_loss = read.csv(paste0(basefspath, "/eval/datasets/basefs-loss.csv"))
basefs_loss_completed = read.csv(paste0(basefspath, "/eval/datasets/basefs-loss-completed.csv"))

for (var in c("loss", "bw", "delay", "reorder")) {
    do_graphs(gossip, gossip_completed, var, 'gossip')
}
do_graphs(basefs_loss, basefs_loss_completed, 'loss', 'basefs')
