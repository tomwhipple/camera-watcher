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

RUN mkdir -p /app/camera-watcher

WORKDIR /app/camera-watcher

COPY *.py ./

COPY application.cfg ./
COPY docker-start.sh ./
COPY etc etc/
COPY watcher watcher/

RUN mkdir -p /data
RUN mkdir -p /var/log/redis

CMD ./docker-start.sh

EXPOSE 6379
