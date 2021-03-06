#!/usr/bin/Rscript


library(ggplot2)
library(ggthemes)
library(Hmisc)
library(tidyr)
library(reshape2)

basefspath = Sys.getenv("BASEFSPATH")
args = commandArgs(trailingOnly=TRUE)
black <- args[1] == "black"
extra <- ''
if ( is.na(black) ){
    black <- FALSE
} else if ( black ) {
    extra <- '-black'
}

multiplot <- function(..., plotlist=NULL, file, cols=1, layout=NULL) {
  library(grid)
  plots <- c(list(...), plotlist)
  numPlots = length(plots)
  if (is.null(layout)) {
    layout <- matrix(seq(1, cols * ceiling(numPlots/cols)),
                    ncol = cols, nrow = ceiling(numPlots/cols))
  }
 if (numPlots==1) {
    print(plots[[1]])
  } else {
    grid.newpage()
    pushViewport(viewport(layout = grid.layout(nrow(layout), ncol(layout))))
    for (i in 1:numPlots) {
      matchidx <- as.data.frame(which(layout == i, arr.ind = TRUE))
      print(plots[[i]], vp = viewport(layout.pos.row = matchidx$row,
                                      layout.pos.col = matchidx$col))
    }
  }
}

do_graph <- function(name, verbose) {
    dataset = read.csv(paste0(basefspath, "/eval/datasets/basefs-", name, ".csv"))
    plot <- ggplot(data=dataset, aes(x=time)) +
      stat_ecdf(aes(color=factor(size+1)), size=1) +
      stat_ecdf(size=1, alpha=0.7) +
      ggtitle(verbose) +
      xlim(0, 5) +
      labs(x="Time in seconds", y="Convergence %", colour="Entries")
    if ( ! black ) plot <- plot + theme_bw()
#    ggsave(paste0(basefspath, "/eval/plots/basefs-", name, ".png"), dpi=600)
#    print(paste0("eog ", basefspath, "/eval/plots/basefs-", name, ".png"))
    if ( name == 'confine' ) {
        plot <- plot + theme(legend.position = "none")
    } else {
        plot <- plot + theme(axis.title.y=element_blank(), legend.key=element_blank())
    }
    plot
}


plt1 <- do_graph("confine", "CommunityLab")
plt2 <- do_graph("docker", "Docker")


png(paste0(basefspath, "/eval/plots/basefs", extra, ".png"), width=8, height=6, units="in", res=600)
multiplot(plt1, plt2, cols=2);
dev.off()
print(paste0("eog ", basefspath, "/eval/plots/basefs", extra, ".png"))


do_graph <- function(name, verbose) {
#    xx = read.csv(paste0(basefspath, "eval/datasets/basefs-", name, "-traffic.csv"))
#    traffic = gather(xx, "variable", "value", -Timestamp)
#    traffic$Bytes = grepl("bytes", traffic$variable)
#    traffic$Bytes = factor(ifelse(traffic$Bytes, "Bytes", "Packets"))
#    traffic$variable = gsub(".bytes", "", traffic$variable, fixed = T)
#    traffic$variable = gsub(".pkts", "", traffic$variable, fixed = T)
#    traffic$variable = gsub(".", " ", traffic$variable, fixed = T)
#    traffic$Timestamp = traffic$Timestamp - min(traffic$Timestamp)
#    ggplot(traffic, aes(x=Timestamp, fill=variable, y=value)) +
#        geom_area(position="identity", alpha=0.7) +
#        facet_wrap(~Bytes, scales="free_y") +
#        theme_bw() +
#        scale_fill_tableau()
#    traffic_path = paste0(basefspath, "eval/plots/basefs-", name, "-traffic.png")
#    ggsave(traffic_path, dpi=600)
#    print(paste0('eog ', traffic_path))

    breaks = c(
        "Serf.UDP.bytes",
        "Serf.TCP.bytes",
        "Sync.bytes"
    )
    labels = c(
        "Serf UDP",
        "Serf TCP",
        "Sync"
    )

    xx = read.csv(paste0(basefspath, "eval/datasets/basefs-", name, "-traffic-distribution.csv"))
    traffic<- melt(xx, id.var="Node")
    traffic$variable = factor(traffic$variable, levels=breaks)
    levels(traffic$variable) = labels
    plot <- ggplot(traffic, aes(x=Node, y=value/10**6, fill=variable)) +
        geom_bar(stat = "identity", position="dodge") +
        ggtitle(verbose) +
        ylim(0, 7.5)
    if ( ! black ) plot <- plot + theme_bw()
    if ( name == 'confine' ) {
        plot <- plot +
            theme(legend.position = "none") +
            labs(x="Node", y="Traffic in MB")
    } else {
        plot <- plot +
            labs(x="Node") +
            scale_fill_discrete(name="Protocol") +
            theme(axis.title.y=element_blank(), legend.key=element_blank())
    }
    plot
}

plt1 <- do_graph("confine", "CommunityLab")
plt2 <- do_graph("docker", "Docker")

png(paste0(basefspath, "/eval/plots/basefs-traffic-distribution", extra, ".png"), width=8, height=6, units="in", res=600)
multiplot(plt1, plt2, cols=2);
dev.off()
print(paste0("eog ", basefspath, "/eval/plots/basefs-traffic-distribution", extra, ".png"))

