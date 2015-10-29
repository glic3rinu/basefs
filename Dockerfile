FROM debian:latest
RUN apt-get -y update && apt-get install -y curl sudo nano net-tools unzip python3-pip libfuse2
RUN curl -L https://dl.bintray.com/mitchellh/serf/0.6.4_linux_amd64.zip > /tmp/serf.zip && unzip /tmp/serf.zip -d /usr/bin/
RUN pip3 install serfclient ecdsa fusepy
