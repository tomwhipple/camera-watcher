#! /usr/bin/env bash

test -f /data/watcher.sqlite3 || sqlite3 /data/watcher.sqlite3 -init db/watcher.sql

redis-server etc/redis.conf
motion -c etc/motion/motion.conf -b

rq worker -s video default 2>&1 >> /var/log/video-worker.log

./watchutil.py ioworker 2>&1 >> /var/log/io-worker.log &

wait -n

exit $?
