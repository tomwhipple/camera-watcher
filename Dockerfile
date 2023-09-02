FROM python:3-bookworm


## OS dependencies

RUN apt-get update

RUN apt-get -y install autoconf automake libtool
RUN apt-get -y install autopoint libjpeg-dev libmicrohttpd-dev
RUN apt-get -y install libavutil-dev libavformat-dev libavcodec-dev libswscale-dev libavdevice-dev 


## source dependencies

WORKDIR /app

RUN git clone https://github.com/Motion-Project/motion.git

WORKDIR /app/motion
RUN autoreconf -fiv
RUN ./configure
RUN make -j 16 install


## python requirements

WORKDIR /app
COPY requirements.txt ./
RUN python3 -m pip install -r requirements.txt


## Our code & python dependencies
RUN git clone https://github.com/tomwhipple/camera-watcher.git

WORKDIR /app/camera-watcher

