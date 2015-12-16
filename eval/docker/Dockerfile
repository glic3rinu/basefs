FROM serf

RUN basefs genkey
RUN basefs get test 172.17.42.1
RUN mkdir /tmp/test && basefs mount test /tmp/test -d
