#!/usr/bin/Rscript


library(ggplot2)
library(ggthemes)
library(Hmisc)

basefspath = Sys.getenv("BASEFSPATH")
sync = read.csv(paste0(basefspath, "/eval/datasets/sync.csv"))
sync <- sync[sync$messages!=0,]

plt1 <- ggplot(data=sync, aes(x=scenario, y=time))+
    geom_point(alpha=0.5) +
    stat_summary(fun.data = "mean_cl_boot", size=1, alpha=0.5, geom="line") +
    stat_summary(fun.data = "mean_cl_boot", size=1, alpha=0.5) +
    theme(legend.position="bottom") +
    scale_x_log10() +
    ggtitle("Sync Convergence Time")

#    ggplot(data=sync, aes(x=size+1, y=time, color=factor(scenario)))+
#      geom_point(alpha=0.1) + stat_summary(fun.data = "mean_cl_boot", size=2, alpha=0.5) +
#      scale_x_log10()
#    ggsave("sync.png", dpi=600)

traffic = read.csv(paste0(basefspath, "/eval/datasets/sync-traffic.csv"))

plt2 <- ggplot(data=traffic, aes(x=scenario, y=bps))+
    geom_point(alpha=0.5) +
    stat_summary(fun.data = "mean_cl_boot", size=1, alpha=0.5, geom="line") +
    stat_summary(fun.data = "mean_cl_boot", size=1, alpha=0.5) +
    scale_x_log10() + 
    ggtitle("Sync Traffic Usage")


# Multiple plot function
#
# ggplot objects can be passed in ..., or to plotlist (as a list of ggplot objects)
# - cols:   Number of columns in layout
# - layout: A matrix specifying the layout. If present, 'cols' is ignored.
#
# If the layout is something like matrix(c(1,2,3,3), nrow=2, byrow=TRUE),
# then plot 1 will go in the upper left, 2 will go in the upper right, and
# 3 will go all the way across the bottom.
#
multiplot <- function(..., plotlist=NULL, file, cols=1, layout=NULL) {
  library(grid)

  # Make a list from the ... arguments and plotlist
  plots <- c(list(...), plotlist)

  numPlots = length(plots)

  # If layout is NULL, then use 'cols' to determine layout
  if (is.null(layout)) {
    # Make the panel
    # ncol: Number of columns of plots
    # nrow: Number of rows needed, calculated from # of cols
    layout <- matrix(seq(1, cols * ceiling(numPlots/cols)),
                    ncol = cols, nrow = ceiling(numPlots/cols))
  }
 if (numPlots==1) {
    print(plots[[1]])
  } else {
    # Set up the page
    grid.newpage()
    pushViewport(viewport(layout = grid.layout(nrow(layout), ncol(layout))))
    # Make each plot, in the correct location
    for (i in 1:numPlots) {
      # Get the i,j matrix positions of the regions that contain this subplot
      matchidx <- as.data.frame(which(layout == i, arr.ind = TRUE))
      print(plots[[i]], vp = viewport(layout.pos.row = matchidx$row,
                                      layout.pos.col = matchidx$col))
    }
  }
}
png(paste0(basefspath, "/eval/plots/sync.png"),width=8,height=6,units="in",res=600)
multiplot(plt1, plt2, cols=2);
dev.off()
print(paste0("eog ", basefspath, "/eval/plots/sync.png"))
