FROM debian:latest

RUN apt-get update

RUN apt-get -y update && apt-get install -y --force-yes \
    libfuse2 \
    python3-pip \
    netcat-openbsd \
    iptables \
    net-tools

RUN apt-get clean
RUN pip3 install https://github.com/glic3rinu/basefs/tarball/master#egg=basefs-dev

RUN apt-get -y remove build-essential
RUN apt-get -y autoremove
RUN apt-get clean

RUN rm -r /usr/local/lib/python3.4/dist-packages/basefs
RUN echo '/mnt/' > /usr/local/lib/python3.4/dist-packages/basefs.pth
RUN rm /usr/local/bin/basefs && ln -s /mnt/basefs/bin/basefs /usr/local/bin/
