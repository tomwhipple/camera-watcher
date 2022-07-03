
import os, sys 

import configparser
import requests
import logging

from time import time, sleep

# This is built to wait for a satallite to boot up, acquire signal and be ready to go. It takes a while.
CONNECTION_TIMEOUT_MINUTES = 30

PI_MODEL_FILE='/sys/firmware/devicetree/base/model'
def is_raspi():
    if not os.access(PI_MODEL_FILE, os.R_OK):
        return False

    with open(PI_MODEL_FILE) as rpi:
        rpi_version = rpi.read()

        return rpi_version.startswith("Raspberry Pi")


if is_raspi():
    from gpiozero import LED

class NetworkPowerSwitch(object):
    logger = None

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        config = configparser.ConfigParser()
        config.read(os.path.join(sys.path[0],'application.cfg'))

        self.relay = None
        if 'hardware' in config:
            pin = config['hardware'].getint('INTERNET_RELAY_PIN', -1)
            if is_raspi() and pin >= 0:
                self.relay = LED(pin)

        self.check_url = config.get('remote','SYNC_APP_URL', fallback='http://www.tomwhipple.com') + '/'

    def enable(self):
        if self.relay:
            self.relay.on()
            sleep(1)

        netsession = requests.Session()

        begin_time = time()
        while time() - begin_time < CONNECTION_TIMEOUT_MINUTES * 60:
            try:
                resp = netsession.head(self.check_url)
                self.logger.debug(f"got {resp.status_code} from {self.check_url} ")
                if resp.status_code > 0:
                    resp.close()
                    return
                else:
                    msg = f"{resp.status_code} (not OK) response was recieved: {resp}"
                    print(msg)
                    self.logger.error(msg)

            except (requests.Timeout, requests.ConnectionError) as e:
                self.logger.debug(f"got a {str(e)} - waiting to try again")
                sleep(15)

        raise Exception(f"Timed out waiting for network connection to {self.check_url}")

    def __enter__(self):
        return self.enable()

    def __exit__(self, *args):
        if self.relay:
            self.relay.off()
