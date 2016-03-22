#!/usr/bin/Rscript


library(ggplot2)
library(ggthemes)
library(Hmisc)


basefspath = Sys.getenv("BASEFSPATH")
args = commandArgs(trailingOnly=TRUE)
black <- args[1] == "black"
extra <- ''
if ( is.na(black) ){
    black <- FALSE
} else if ( black ) {
    extra <- '-black'
}


perf <- read.csv(paste0(basefspath, "/eval/datasets/performance2.csv"))
df <- perf[perf$operation=="write",]
df$group = interaction(df$type, df$fs)
breaks = c(
    "file.basefs",
    "mkdir.basefs",
    "link.basefs",
    "file.ext4",
    "mkdir.ext4",
    "link.ext4"
)
labels = c(
    "BaseFS file",
    "BaseFS mkdir",
    "BaseFS link",
    "EXT4 file",
    "EXT4 mkdir",
    "EXT4 link"
)
plt <- ggplot(data=df, aes(x=round, y=time*1000, color=group, shape=group)) +
    geom_point(size=1, alpha=0.5) +
    scale_y_log10() +
    stat_summary(fun.data = "mean_cl_boot", size=1, alpha=1) +
    stat_summary(fun.y = "mean", geom="line") +
    labs(y="Time in ms", x="Round", color="group", main="") +
    scale_color_discrete(name="", labels=labels, breaks=breaks) +
    scale_shape_discrete(name="", labels=labels, breaks=breaks)
if ( ! black ) plt <- plt + theme_bw()
plt

ggsave(paste0(basefspath, "/eval/plots/write_performance", extra, ".png"), dpi=600)
print(paste0("eog ", basefspath, "/eval/plots/write_performance", extra, ".png"))

perf <- read.csv(paste0(basefspath, "/eval/datasets/performance.csv"))
df = perf[perf$operation!="write",]
df$group = interaction(df$operation, df$fs)
breaks = c(
    "read.basefs",
    "read-cached.basefs",
    "read.ext4",
    "read-cached.ext4"
)
labels = c(
    "BaseFS cold read",
    "BaseFS cached read",
    "EXT4 cold read",
    "EXT4 cached read"
)
plt <- ggplot(data=df, aes(x=round, y=time, color=group, shape=group)) +
    geom_line(size=1) +
    geom_point(size=3) +
    labs(y="Time in seconds", x="Round", color="group") +
    scale_color_discrete(name="", labels=labels, breaks=breaks) +
    scale_shape_discrete(name="", labels=labels, breaks=breaks)
if ( ! black ) plt <- plt + theme_bw()
plt
ggsave(paste0(basefspath, "/eval/plots/read_performance", extra, ".png"), dpi=600)
print(paste0("eog ", basefspath, "/eval/plots/read_performance", extra, ".png"))
