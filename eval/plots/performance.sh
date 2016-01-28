#!/bin/bash

. $(dirname "${BASH_SOURCE[0]}")/utils.sh

# perf > /tmp/perf.csv

cat << 'EOF' | Rscript --vanilla - $BASEFSPATH
    library(ggplot2)
    library(ggthemes)
    library(Hmisc)

    perf <- read.csv(paste0(args[1], "/eval/datasets/performance.csv"))
    df <- perf[perf$operation=="write",];
    ggplot(data=df, aes(x=round, y=time, color=fs)) +
      geom_line();
    ggsave(paste0(args[1], "/eval/plots/write_performance.png"), dpi=600)
    print(paste0("eog ", args[1], "/eval/plots/write_performance.png"))

    df = perf[perf$operation!="write",];
    df$group = interaction(df$operation, df$fs);
    ggplot(data=df, aes(x=round, y=time, color=group)) +
      geom_line();

    ggsave(paste0(args[1], "/eval/plots/read_performance.png"), dpi=600)
    print(paste0("eog ", args[1], "/eval/plots/read_performance.png"))

EOF
