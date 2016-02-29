#!/usr/bin/Rscript


library(ggplot2)
library(ggthemes)
library(Hmisc)

basefspath = Sys.getenv("BASEFSPATH")
char = read.csv(paste0(basefspath, "/eval/datasets/characterization.csv"))

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

plt1 <- ggplot(data=char, aes(x=hops)) +
    geom_histogram(alpha=0.7, binwidth=1, fill='cornflowerblue', color='darkblue') +
    theme(legend.position="bottom") +
    labs(y="Number of hops", x="Number of links") +
    theme_bw() +
    ggtitle("Hops per link")


plt2 <- ggplot(data=char, aes(x=latency))+
    geom_density(alpha=0.7, size=1) +
    geom_histogram(aes(y=..density..), alpha=0.5, binwidth=10, fill='cornflowerblue') +
    theme_bw() +
    theme(legend.position="bottom") +
    labs(y="Probability", x="Latency in ms") + 
    ggtitle("Latency distribution")



png(paste0(basefspath, "/eval/plots/characterization.png"), width=8, height=6, units="in", res=600)
multiplot(plt1, plt2, cols=2);
dev.off()
print(paste0("eog ", basefspath, "/eval/plots/characterization.png"))
