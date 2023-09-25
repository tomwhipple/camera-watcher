FROM python:3-bookworm


## OS dependencies

RUN apt-get update

RUN apt-get -y install autoconf automake libtool \
autopoint libjpeg-dev libmicrohttpd-dev \
libavutil-dev libavformat-dev libavcodec-dev libswscale-dev libavdevice-dev \
ffmpeg 


WORKDIR /app

RUN git clone https://github.com/Motion-Project/motion.git

WORKDIR /app/motion
RUN autoreconf -fiv
RUN ./configure
RUN make -j 16 install


## python requirements
WORKDIR /app
RUN python3 -m pip install rq

