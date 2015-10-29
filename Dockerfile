FROM debian:latest

RUN apt-get -y update && apt-get install -y \
    curl \
    libfuse2 \
    nano \
    net-tools \
    python3-pip \
    sudo \
    unzip

RUN curl -L https://dl.bintray.com/mitchellh/serf/0.6.4_linux_amd64.zip > /tmp/serf.zip && \
    unzip /tmp/serf.zip -d /usr/bin/

RUN pip3 install \
    ecdsa \
    fusepy \
    serfclient
