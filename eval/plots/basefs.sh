function graphscenarios () {
    cat << EOF | Rscript -
    library(ggplot2)
    library(ggthemes)
    library(Hmisc)
    
    scenarios = read.csv("$BASEFSPATH/eval/datasets/basefseval.csv")
    ggplot(data=scenarios, aes(x=time)) +
      stat_ecdf(aes(color=factor(size)))+
      stat_ecdf(size=1) +
      ggtitle("BaseFS Convergence")
      
#      stat_summary(fun.y=mean, geom="line") + 
#      geom_line(aes(group=filename), alpha=0.1) +  coord_flip(ylim=c(0,3))
    ggsave("$BASEFSPATH/eval/plots/basefseval.png", dpi=600)
    print("eog $BASEFSPATH/eval/plots/basefseval.png")


#    scenarios = read.csv("$BASEFSPATH/eval/datasets/basefs-completed.csv")
#    ggplot(data=scenarios, aes(x=messages+1, y=completed, color=factor(scenario))) +
#        geom_line() +
#        geom_point() +
#        scale_x_log10()
#    ggsave("$BASEFSPATH/eval/plots/basefs-conv-completed.png", dpi=600)
#    ggplot(data=scenarios, aes(x=messages+1, y=time)) +
#      geom_point(alpha=0.1) + 
#      stat_summary(fun.data = "mean_cl_boot", size=2, alpha=0.5) + 
#      facet_grid(~scenario) +
#      scale_x_log10()
#    ggsave("gossipconv2.png", dpi=600)
EOF
}


graphscenarios


#> scenarios[14325,]
#      scenario size messages    node   time         filename completed
#14325     eval    1        1 node-20 58.112 testfile493-18-1        29
#> xx = scenarios[scenarios$filename!="testfile493-18-1",]
#> xx[which.max(xx$time),]
#    scenario size messages    node   time        filename completed
#319     eval   16       -1 node-15 30.763 testfile10-1-16        29
#> xx = scenarios[scenarios$filename!="testfile10-1-16",]
#> scenarios[14325,+
#>     ggplot(data=xx, aes(x=time, y=completed, color=factor(filename))) +
#+       geom_point() +
#+       geom_line() +
#+     theme(legend.position="none")
#> 
#> 
#> xx[which.max(xx$time),]
#      scenario size messages    node   time         filename completed
#14325     eval    1        1 node-20 58.112 testfile493-18-1        29
#> xx = xx[xx$filename!="testfile493-18-1",]
#>     ggplot(data=xx, aes(x=time, y=completed, color=factor(filename))) +
#+       geom_point() +
#+       geom_line() +
#+     theme(legend.position="none")

