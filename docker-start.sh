#! /usr/bin/env bash

test -f /data/watcher.sqlite3 || sqlite3 /data/watcher.sqlite3 -init db/watcher.sql

redis-server etc/redis.conf
motion -c etc/motion/motion.conf -b

./watchutil.py ioworker &
./rq worker -s video default &
