#!/usr/bin/env python3

from flup.server.fcgi import WSGIServer
from logging.config import dictConfig

import logging
import configparser
import os

from api import app

if __name__ == '__main__':
    config = configparser.ConfigParser()
    file = os.path.join(sys.path[0],'application.cfg')
    config.read(file)

    logfile = config['system'].get('LOGFILE', 'watcher.log')

    if os.access(logfile, os.W_OK):
        app.logger.addHandler(logging.FileHandler())
    else:
        print(f"Can't open {logfile} for writing")

    dictConfig({
        'version': 1,
        'formatters': {'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }},
        'handlers': {'wsgi': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://flask.logging.wsgi_errors_stream',
            'formatter': 'default'
        }},
        'root': {
            'level': 'INFO',
            'handlers': ['wsgi']
        }
    })

    WSGIServer(app).run()
