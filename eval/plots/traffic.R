#!/usr/bin/Rscript


library("ggthemes")
library("ggplot2")
library("tidyr")
library("reshape2")


basefspath = Sys.getenv("BASEFSPATH")

do_graph <- function(name) {
    xx = read.csv(paste0(basefspath, "eval/datasets/basefs-", name, "-traffic.csv"))
    traffic = gather(xx, "variable", "value", -Timestamp)
    traffic$Bytes = grepl("bytes", traffic$variable)
    traffic$Bytes = factor(ifelse(traffic$Bytes, "Bytes", "Packets"))
    traffic$variable = gsub(".bytes", "", traffic$variable, fixed = T)
    traffic$variable = gsub(".pkts", "", traffic$variable, fixed = T)
    traffic$variable = gsub(".", " ", traffic$variable, fixed = T)
    traffic$Timestamp = traffic$Timestamp - min(traffic$Timestamp)
    ggplot(traffic, aes(x=Timestamp, fill=variable, y=value)) +
        geom_area(position="identity", alpha=0.7) +
        facet_wrap(~Bytes, scales="free_y") +
        theme_bw() +
        scale_fill_tableau()
    traffic_path = paste0(basefspath, "eval/plots/basefs-", name, "-traffic.png")
    ggsave(traffic_path, dpi=600)
    print(paste0('eog ', traffic_path))

    xx = read.csv(paste0(basefspath, "eval/datasets/basefs-", name, "-traffic-distribution.csv"))
    traffic<- melt(xx, id.var="Node")
    ggplot(traffic, aes(x = Node, y = value, fill = variable)) + 
        geom_bar(stat = "identity")
    traffic_distribution_path = paste0(basefspath, "eval/plots/basefs-", name, "-traffic-distribution.png")
    ggsave(traffic_distribution_path, dpi=600)
    print(paste0('eog ', traffic_distribution_path))
}

do_graph('confine')
do_graph('docker')
