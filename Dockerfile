FROM debian:latest

RUN apt-get -y update && apt-get install -y \
    libfuse2 \
    python3-pip
#    screen
#    net-tools \
#    nano

RUN pip3 install basefs==1-dev  \
    --allow-external basefs \
    --allow-unverified basefs
