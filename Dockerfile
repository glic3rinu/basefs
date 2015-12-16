FROM debian:latest

RUN apt-get update

RUN apt-get -y update && apt-get install -y \
    libfuse2 \
    python3-pip \
    netcat-openbsd
#    screen
#    net-tools \
#    nano

RUN pip3 install basefs==1-dev \
    --allow-external basefs  \
    --allow-unverified basefs

# Don't know why pip fails with ImportError: No module named 'fuse' :(
RUN basefs installserf

RUN rm -r /usr/local/lib/python3.4/dist-packages/basefs
RUN echo '/mnt/' > /usr/local/lib/python3.4/dist-packages/basefs.pth
RUN rm /usr/local/bin/basefs && ln -s /mnt/basefs/bin/basefs /usr/local/bin/
