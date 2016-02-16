#!/usr/bin/Rscript


library(ggplot2)
library(ggthemes)
library(Hmisc)


basefspath = Sys.getenv("BASEFSPATH")

perf <- read.csv(paste0(basefspath, "/eval/datasets/performance.csv"))
df <- perf[perf$operation=="write",]
ggplot(data=df, aes(x=round, y=time, color=fs)) +
    geom_line(size=1) +
    geom_point(size=3) +
    scale_y_log10() +
    ggtitle("BaseFS vs EXT4 Write Performance") +
    labs(y="Time in Seconds", x="Round", color="Filesystem")

ggsave(paste0(basefspath, "/eval/plots/write_performance.png"), dpi=600)
print(paste0("eog ", basefspath, "/eval/plots/write_performance.png"))

df = perf[perf$operation!="write",]
df$group = interaction(df$operation, df$fs)

ggplot(data=df, aes(x=round, y=time, color=group)) +
    geom_line(size=1) +
    geom_point(size=3) +
    scale_y_log10() +
    ggtitle("BaseFS vs EXT4 Read Performance") +
    labs(y="Time in Seconds") +
    labs(x="Round")

ggsave(paste0(basefspath, "/eval/plots/read_performance.png"), dpi=600)
print(paste0("eog ", basefspath, "/eval/plots/read_performance.png"))
