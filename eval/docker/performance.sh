#!/bin/bash

. $(dirname "${BASH_SOURCE[0]}")/utils.sh

function perf () {
    echo "fs,operation,round,time"
    num=1
    grep real basefs-write | awk {'print $2'} | sed -e "s/m/*60+/" -e "s/s//" | bc | awk '{printf "%f\n", $0}' | while read line; do
        echo "basefs,write,$num,$line";
        num=$(($num+1));
    done
    num=1
    grep real basefs-read | awk {'print $2'} | sed -e "s/m/*60+/" -e "s/s//" | bc | awk '{printf "%f\n", $0}' | while read line; do
        echo "basefs,read,$num,$line";
        num=$(($num+1));
    done
    num=1
    grep real basefs-read2 | awk {'print $2'} | sed -e "s/m/*60+/" -e "s/s//" | bc | awk '{printf "%f\n", $0}' | while read line; do
        echo "basefs,read-cached,$num,$line";
        num=$(($num+1));
    done

    num=1
    grep real ext4-write | awk {'print $2'} | sed -e "s/m/*60+/" -e "s/s//" | bc | awk '{printf "%f\n", $0}' | while read line; do
        echo "ext4,write,$num,$line";
        num=$(($num+1));
    done
    num=1
    grep real ext4-read | awk {'print $2'} | sed -e "s/m/*60+/" -e "s/s//" | bc | awk '{printf "%f\n", $0}' | while read line; do
        echo "ext4,read,$num,$line";
        num=$(($num+1));
    done
    num=1
    grep real ext4-read2 | awk {'print $2'} | sed -e "s/m/*60+/" -e "s/s//" | bc | awk '{printf "%f\n", $0}' | while read line; do
        echo "ext4,read-cached,$num,$line";
        num=$(($num+1));
    done
}

# perf > /tmp/perf.csv

cat << 'EOF' | Rscript -
library(ggplot2)
library(ggthemes)
library(Hmisc)

perf <- read.csv("/tmp/perf.csv");
df <- perf[perf$operation=="write",];
ggplot(data=df, aes(x=round, y=time, color=fs)) +
  geom_line();
ggsave("write_performance.png", dpi=600);

df = perf[perf$operation!="write",];
df$group = interaction(df$operation, df$fs);
ggplot(data=df, aes(x=round, y=time, color=group)) +
  geom_line();

ggsave("read_performance.png", dpi=600);

EOF
