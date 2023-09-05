#! /usr/bin/env bash

redis-server etc/redis.conf
motion -c etc/motion/motion.conf -b

./watchutil.py ioworker &
./rq worker -s video default &
