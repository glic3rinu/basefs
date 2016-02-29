#!/usr/bin/Rscript


library(ggplot2)
library(ggthemes)
library(Hmisc)

basefspath = Sys.getenv("BASEFSPATH")


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

scalability = read.csv(paste0(basefspath, "/eval/datasets/scalability.csv"))
plt1 <- ggplot(data=scalability, aes(x=scenario+1, y=time)) + #, color=factor(scenario))) +
    geom_point(alpha=0.7, color='cornflowerblue') +
    stat_summary(fun.data = "mean_cl_boot", size=1, alpha=0.7, geom="line") +
    theme_bw() +
    scale_x_continuous(breaks=c(0, 30, 50, 100, 150, 200, 250, 300, 350, 400)) +
    stat_summary(fun.data = "mean_cl_boot", size=1, alpha=0.7) +
    labs(y="Time in seconds", x="Number of Nodes") +
    theme(legend.position = "none") +
    ggtitle("Convergence Time")


#overhead = read.csv(paste0(basefspath, "/eval/datasets/scalability-overhead.csv"))
#plt2 <- ggplot(data=overhead, aes(x=scenario+1, y=time, color=factor(metric))) +
#    geom_point(alpha=0.5) +
#    stat_summary(fun.data = "mean_cl_boot", size=1, alpha=0.5, geom="line") +
#    stat_summary(fun.data = "mean_cl_boot", size=1, alpha=0.5) +
#    labs(y="Time in seconds", x="Number of Nodes") +
#    theme(legend.position = "bottom") +
#    ggtitle("Complition Time")


load = read.csv(paste0(basefspath, "/eval/datasets/scalability-load.csv"))
load <- load[load$slot==-1,]
plt2 <- ggplot(data=load, aes(x=scenario+1, y=one_min, color='red')) + #factor(slot))) +
    geom_point(alpha=0.7) +
    scale_y_continuous(breaks=c(0, 50, 100, 150, 200, 250, 300, 350, 400)) +
    scale_x_continuous(breaks=c(0, 30, 50, 100, 150, 200, 250, 300, 350, 400)) +
    theme_bw() +
    geom_hline(yintercept=4, alpha=0.4, color='blue') +
    geom_vline(xintercept=45, alpha=0.4, color='blue') +
    stat_summary(fun.data = "mean_cl_boot", size=1, alpha=0.7, geom="line") +
    stat_summary(fun.data = "mean_cl_boot", size=1, alpha=0.7) +
    labs(y="Load AVG", x="Number of Nodes") +
    theme(legend.position = "none") +
    ggtitle("Load AVG over last minute")



png(paste0(basefspath, "/eval/plots/scalability.png"), width=8, height=6, units="in", res=600)
multiplot(plt1, plt2, cols=2);
dev.off()
print(paste0("eog ", basefspath, "/eval/plots/scalability.png"))
