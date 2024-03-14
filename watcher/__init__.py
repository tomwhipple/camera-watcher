from . import model
from . import connection

from .model import *
from .connection import *
from .remote import *
from .outdoors import *

__all__ = (model.__all__ + connection.__all__ + remote.__all__ + outdoors.__all__)
__all__.append(['setup_logging', 'get_local_time_iso'])

import logging
import sys
from pathlib import Path

logfile = Path('log/watcher/watcher.log')
logname = 'watcher'
logger = None
    
def setup_logging():
    global logger

    if logger != None:
        return logger

    log_level = application_config('log', 'LEVEL').upper()
    assert log_level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], f"invalid log level {log_level}"

    logger = logging.getLogger(logname)
    logger.setLevel(log_level)

    formatter = logging.Formatter('[%(asctime)s] %(name)s %(levelname)s: %(message)s')

    consoleHandler = logging.StreamHandler()
    consoleHandler.setLevel(log_level)
    #consoleHandler.setFormatter(formatter)
    consoleHandler.setStream(sys.stdout)

    if not logfile.parent.exists():
        logfile.parent.mkdir(parents=True, exist_ok=True)

    fileHandler = logging.FileHandler(logfile)
    fileHandler.setLevel(log_level)
    fileHandler.setFormatter(formatter)

    logger.addHandler(consoleHandler)
    logger.addHandler(fileHandler)

    return logger

