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


exclude = c(
    "bw-256kbit", 
    "bw-32kbit-htb1", 
    'bw-64kbit-htb1',
    'bw-56kbit',
    'bw-512kbit',
    'bw-1mbit',
    'bw-512',
    'bw-256',
    'bw-1024',
    'bw-54',
    'bw-2',
    'delay-20ms',
    'delay-300ms',
    'delay-400ms',
    'delay-600ms',
    'delay-2000',
    'delay-2500',
    'delay-3000',
    'delay-10',
    'delay-20',
    'delay-40',
    'delay-80',
    'delay-320',
    'loss-10',
    'loss-20',
    'loss-30',
    'loss-40'
#    'baseline'
)


get_breaks = function(values){
    breaks10 = log_breaks()(values)
    as.vector(t(sapply(c(1,2,5), function(x) x*breaks10)))
}



#do_graphs <- function (dataset, dataset_completed, var, name) {
#    current <- dataset[grepl(var, dataset$scenario) | dataset$scenario=="baseline",]
#    current = current[! current$scenario %in% exclude,]
##    current$scenario[current$scenario == "delay-100ms"] <- '1000'
#    ggplot(data=current, aes(x=size, y=time, color=factor(round))) +
#        geom_point(alpha=0.5) +
#        stat_summary(fun.data="mean_cl_boot", size=1, alpha=0.5) +
#        scale_x_log10() +
#        scale_y_log10() +
#        ggtitle(paste0(name, " - ", "convergence time under variable ", var)) +
#        labs(y="Time in seconds", x="Log entries", colour="Delay")
#    
#    ggsave(paste0(basefspath, "/eval/plots/", name, "-", var, ".png"), dpi=600)
#    print(paste0("eog ", basefspath, "/eval/plots/", name, "-", var, ".png"))



do_graphs <- function (dataset, dataset_completed, var, name, verbose) {
    current <- dataset[grepl(var[1], dataset$scenario) | dataset$scenario=="baseline",]
    current = current[! current$scenario %in% exclude,]
    numbers = sort(as.numeric(levels(current$round)))
    if ( var[1] == "bw" ) {
        numbers <- rev(numbers)
    }
    current$Color = ordered(current$round, levels=c("baseline", numbers))
    levels(current$Color) = ifelse(levels(current$Color)=="baseline", 
                                    levels(current$Color),
                                    paste0(levels(current$Color), var[3]))
#    current$scenario[current$scenario == "delay-100ms"] <- '1000'
    guide = guide_legend(title=var[2], keywidth=3, keyheight=1)
    plt = ggplot(data=current, aes(x=size, y=time, color=Color, linetype=Color)) +
        geom_point(alpha=0.5) +
        stat_summary(fun.data="mean_cl_boot", size=1, alpha=0.5, aes(shape=Color)) +
        stat_summary(fun.y="mean", geom="line") +
        scale_x_log10(breaks=get_breaks) +
        scale_y_log10(breaks=get_breaks, labels=as.character) +
        labs(y="Time in seconds", x="Log entries") + 
        guides(color=guide, linetype=guide, shape=guide) +
        theme(legend.key=element_blank())
    if ( ! black ) plt + theme_bw() + theme(legend.key=element_blank())
    ggsave(paste0(basefspath, "/eval/plots/", name, "-", var[1], extra, ".png"), dpi=600)
    print(paste0("eog ", basefspath, "/eval/plots/", name, "-", var[1], extra, ".png"))
    
    current <- dataset_completed[grepl(var[1],dataset_completed$scenario) | dataset_completed$scenario=="baseline",]
    current = current[! current$scenario  %in% exclude,]
    numbers = sort(as.numeric(levels(current$round)))
    current$Color = ordered(current$round, levels=c("baseline", numbers))
    levels(current$Color) = ifelse(levels(current$Color)=="baseline", 
                                    levels(current$Color),
                                    paste0(levels(current$Color), var[3]))
    plt <- ggplot(data=current, aes(x=size, y=completed, color=Color, linetype=Color)) +
        geom_point(size=3, aes(shape=Color)) +
        geom_line() +
        scale_x_log10() +
        guides(color=guide, linetype=guide, shape=guide) +
        theme(legend.key=element_blank()) +
        labs(y="Number of completed nodes", x="Log entries")
    if ( ! black ) plt + theme_bw() + theme(legend.key=element_blank())
    ggsave(paste0(basefspath, "/eval/plots/", name, "-", var[1], "-completed", extra, ".png"), dpi=600)
    print(paste0("eog ", basefspath, "/eval/plots/", name, "-", var[1], "-completed", extra, ".png"))
}



gossip = read.csv(paste0(basefspath, "/eval/datasets/gossip.csv"))
gossip_completed = read.csv(paste0(basefspath, "/eval/datasets/gossip-completed.csv"))

basefs = read.csv(paste0(basefspath, "/eval/datasets/basefs.csv"))
basefs_completed = read.csv(paste0(basefspath, "/eval/datasets/basefs-completed.csv"))


vars = list(
    c("loss", "Packet Loss", "%"),
    c("bw", "Bandwidth", "Kbps"),
    c("reorder", "Packet Reorder", "%"),
    c("delay", "Mean Delay", "ms")
)

#for (var in vars) {
#    do_graphs(gossip, gossip_completed, var, 'gossip', 'Gossip')
#}
for (var in vars){
    do_graphs(basefs, basefs_completed, var, 'basefs', 'BaseFS')
}


