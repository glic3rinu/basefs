library("ggthemes")
library("ggplot2")
library("tidyr")


xx = read.csv("traffic.csv")
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
