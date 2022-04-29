#!/usr/bin/env python3

from flup.server.fcgi import WSGIServer
from api import app

if __name__ == '__main__':
    app.logger.addHandler(logging.FileHandler('/var/log/lighttpd/watcher.log'))
    app.logger.setLevel(logging.INFO)

    WSGIServer(app).run()
