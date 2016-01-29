#!/usr/bin/Rscript


library(ggplot2)
library(ggthemes)
library(Hmisc)

basefspath = Sys.getenv("BASEFSPATH")

do_graph <- function(name) {
    dataset = read.csv(paste0(basefspath, "/eval/datasets/basefs-", name, ".csv"))
    ggplot(data=dataset, aes(x=time)) +
      stat_ecdf(aes(color=factor(size)))+
      stat_ecdf(size=1) +
      ggtitle(paste0("BaseFS Convergence - ", name))

    ggsave(paste0(basefspath, "/eval/plots/basefs-", name, ".png"), dpi=600)
    print(paste0("eog ", basefspath, "/eval/plots/basefs-", name, ".png"))
}

do_graph("docker")
do_graph("confine")
