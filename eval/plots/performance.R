#!/usr/bin/Rscript


library(ggplot2)
library(ggthemes)
library(Hmisc)


basefspath = Sys.getenv("BASEFSPATH")


perf <- read.csv(paste0(basefspath, "/eval/datasets/performance2.csv"))
df <- perf[perf$operation=="write",]
df$group = interaction(df$type, df$fs)
ggplot(data=df, aes(x=round, y=time*1000, color=group, shape=group)) +
    geom_point(size=1, alpha=0.5) +
    scale_y_log10() +
    theme_bw() +
    stat_summary(fun.data = "mean_cl_boot", size=1, alpha=1) +
    stat_summary(fun.y = "mean", geom="line") +
    labs(y="Time in ms", x="Round", color="group")

ggsave(paste0(basefspath, "/eval/plots/write_performance.png"), dpi=600)
print(paste0("eog ", basefspath, "/eval/plots/write_performance.png"))

perf <- read.csv(paste0(basefspath, "/eval/datasets/performance.csv"))
df = perf[perf$operation!="write",]
df$group = interaction(df$operation, df$fs)

ggplot(data=df, aes(x=round, y=time, color=group, shape=group)) +
    geom_line(size=1) +
    geom_point(size=3) +
    theme_bw() +
    labs(y="Time in seconds", x="Round", color="group")

ggsave(paste0(basefspath, "/eval/plots/read_performance.png"), dpi=600)
print(paste0("eog ", basefspath, "/eval/plots/read_performance.png"))
