#!/usr/bin/env python3

import logging
import configparser
import os, sys

from flup.server.fcgi import WSGIServer
from pathlib import Path

from api import app

if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read(os.path.join(sys.path[0],'application.cfg'))

    logpath = Path(config['system'].get('LOGFILE', 'watcher.log'))

    if os.access(logpath, os.W_OK):
        log_handler = logging.FileHandler(logpath)
        log_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s'))
        app.logger.addHandler(log_handler)

    app.logger.setLevel(logging.INFO)

    WSGIServer(app).run()
