#!/usr/bin/Rscript

library(ggplot2)
library(tidyr)


basefspath = Sys.getenv("BASEFSPATH")
args = commandArgs(trailingOnly=TRUE)
black <- args[1] == "black"
extra <- ''
if ( is.na(black) ){
    black <- FALSE
} else if ( black ) {
    extra <- '-black'
}


data = read.csv(paste0(basefspath, "/eval/datasets/etc.csv"))
data.msgs = data[data$type=="messages",]
data.time = data[data$type=="times",]


plt <- ggplot(data.msgs, aes(value, color=method, shape=method, linetype=method)) +
    stat_ecdf(geom="step", alpha=0.7, size=1) +
    stat_ecdf(geom="point", size=3) +
    scale_y_continuous(breaks=c(0.7, 0.8, 0.9, 0.987, 1.0)) +
    geom_hline(yintercept=0.987, alpha=0.4, color='blue') +
    geom_vline(xintercept=10, alpha=0.4, color='blue') +
    scale_x_log10() +
    geom_rug(aes(y=0),position="jitter", sides="b") +
    coord_cartesian(ylim=c(0.70, 1)) +
    labs(y="Probability", x="Messages") + theme(legend.key=element_blank())
if ( ! black ) plt <- plt + theme_bw() + theme(legend.key=element_blank())
plt

ggsave(paste0(basefspath, "eval/plots/etc_messages", extra, ".png"), dpi=600)
print(paste0("eog ", basefspath, "eval/plots/etc_messages", extra, ".png"))

plt <- ggplot(data.time, aes(y=value*1000, x=method, color=method, )) +
    geom_jitter() +
    geom_boxplot(alpha=0.7) +
    coord_flip(ylim=c(0, 16)) +
    labs(y="Time in ms", x='') +
    theme(legend.position="none",
        axis.text.y=element_text(vjust=0.5, size=12))
if ( ! black ) plt <- plt + theme_bw() + theme(legend.position="none",
        axis.text.y=element_text(vjust=0.5, size=12))
plt

ggsave(paste0(basefspath, "eval/plots/etc_time", extra, ".png"), dpi=600)
print(paste0("eog ", basefspath, "eval/plots/etc_time", extra, ".png"))
