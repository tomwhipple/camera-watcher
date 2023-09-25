FROM python:3-bookworm

## OS dependencies

RUN apt-get update
RUN apt-get -y install sqlite3 redis
RUN apt-get -y install libgl-dev


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
