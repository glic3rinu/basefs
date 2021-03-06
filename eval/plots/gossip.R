#!/usr/bin/Rscript


library(ggplot2)
library(ggthemes)
library(Hmisc)
library(scales)

basefspath = Sys.getenv("BASEFSPATH")
args = commandArgs(trailingOnly=TRUE)
black <- args[1] == "black"
extra <- ''
if ( is.na(black) ){
    black <- FALSE
} else if ( black ) {
    extra <- '-black'
}


get_breaks = function(values){
    breaks10 = log_breaks()(values)
    as.vector(t(sapply(c(1,2,5), function(x) x*breaks10)))
}

dataset = read.csv(paste0(basefspath, "/eval/datasets/gossip.csv"))
current <- dataset[grepl('reorder', dataset$scenario) | dataset$scenario=="baseline",]
numbers = sort(as.numeric(levels(current$round)))
current$Color = ordered(current$round, levels=c("baseline", numbers))
levels(current$Color) = ifelse(levels(current$Color)=="baseline", 
                                levels(current$Color),
                                paste0(levels(current$Color), '%'))
#guide = guide_legend(title="", keywidth=3, keyheight=1)
plt = ggplot(data=current, aes(x=size, y=time, color=Color, linetype=Color)) +
    geom_point(alpha=0.5) +
    stat_summary(fun.data="mean_cl_boot", size=1, alpha=0.5, aes(shape=Color)) +
    stat_summary(fun.y="mean", geom="line") +
    scale_x_log10(breaks=get_breaks) +
    scale_y_log10(breaks=get_breaks, labels=as.character) +
    labs(y="Time in seconds", x="Log entries") + 
    geom_hline(yintercept=2, alpha=0.5, color='grey') +
#    geom_segment(aes(x =10, y = 0, xend = 10, yend = 2), alpha=0.4, color='blue') +
    geom_vline(xintercept=10, alpha=0.5, color='grey') +
#    guides(color=guide, linetype=guide, shape=guide) +
    theme(legend.key=element_blank(), legend.position="none")
if ( ! black ) plt <- plt + theme_bw()
plt
ggsave(paste0(basefspath, "/eval/plots/gossip", extra, ".png"), dpi=600)
print(paste0("eog ", basefspath, "/eval/plots/gossip", extra, ".png"))
