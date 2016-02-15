#!/usr/bin/Rscript


library(ggplot2)
library(ggthemes)
library(Hmisc)

basefspath = Sys.getenv("BASEFSPATH")

do_graph <- function(name, verbose) {
    dataset = read.csv(paste0(basefspath, "/eval/datasets/basefs-", name, ".csv"))
    ggplot(data=dataset, aes(x=time)) +
      stat_ecdf(aes(color=factor(size+1)), size=1) +
      stat_ecdf(size=1, alpha=0.7) +
      ggtitle(paste0("BaseFS Convergence - ", verbose)) +
      xlim(0, 5) +
      labs(x="Time in seconds", y="Convergence %", colour="Num mesg")

    ggsave(paste0(basefspath, "/eval/plots/basefs-", name, ".png"), dpi=600)
    print(paste0("eog ", basefspath, "/eval/plots/basefs-", name, ".png"))
}

do_graph("docker", "Docker")
do_graph("confine", "CONFINE")
