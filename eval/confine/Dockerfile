FROM debian:latest

RUN apt-get update

RUN apt-get -y update && apt-get install -y --force-yes \
    libfuse2 \
    python3-pip \
    netcat-openbsd \
    iptables \
    net-tools \
    ntpdate \
    traceroute

RUN pip3 install https://github.com/glic3rinu/basefs/tarball/master#egg=basefs-dev
RUN apt-get -y remove build-essential
RUN apt-get -y autoremove
RUN apt-get clean
