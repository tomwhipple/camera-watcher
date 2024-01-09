FROM python:3-bookworm

## OS dependencies

RUN apt-get update
RUN apt-get -y install sqlite3 redis
RUN apt-get -y install libgl-dev
RUN apt-get -y install ffmpeg

## python requirements
WORKDIR /app
COPY requirements.txt ./
RUN python3 -m pip install -r requirements.txt

## source dependencies

WORKDIR /app

RUN mkdir -p /app/camera-watcher
WORKDIR /app/camera-watcher

COPY *.py ./

COPY application.cfg ./
COPY watcher watcher/

## API support
#COPY _watcher.fcgi ./


## Make a self signed cert for local use
# RUN openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
# -keyout etc/key.pem -out etc/cert.pem \
# -subj '/CN=localhost'