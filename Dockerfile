FROM python:3-bookworm


## OS dependencies

RUN apt-get update

RUN apt-get -y install autoconf automake libtool
RUN apt-get -y install autopoint libjpeg-dev libmicrohttpd-dev
RUN apt-get -y install libavutil-dev libavformat-dev libavcodec-dev libswscale-dev libavdevice-dev 
RUN apt-get -y install sqlite3
RUN apt-get -y install redis ffmpeg


## python requirements
WORKDIR /app
COPY requirements.txt ./
RUN python3 -m pip install -r requirements.txt

## added dependencies

## source dependencies

WORKDIR /app

RUN git clone https://github.com/Motion-Project/motion.git

WORKDIR /app/motion
RUN autoreconf -fiv
RUN ./configure
RUN make -j 16 install


## Our code & python dependencies
WORKDIR /app
RUN git clone https://github.com/tomwhipple/camera-watcher.git

WORKDIR camera-watcher

RUN test -f /data/watcher.sqlite3 || sqlite3 /data/watcher.sqlite3 -init db/watcher.sql
COPY application.cfg ./

COPY etc etc/

RUN mkdir /data

CMD ./docker-start.sh
EXPOSE 6379
