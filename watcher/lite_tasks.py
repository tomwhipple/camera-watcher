import json
import sqlalchemy
from pathlib import Path
from PIL import Image

from rq import Connection, Worker

from .connection import application_config, TunneledConnection, redis_connection
from .model import *

__all__ = ['task_write_image','task_record_event', 'run_io_queues']

connection = TunneledConnection()

def task_write_image(img, img_relpath):
    basedir = Path(application_config('system','BASE_DIR'))
    fullpath = basedir / img_relpath

    fullpath.parent.mkdir(parents=True, exist_ok=True)

    img.save(str(fullpath), quality=85)
    print(f"wrote {fullpath}")

def task_record_event(event_class, input_json_str):
    global connection

    allowed_classes = ['EventObservation', 'MotionEvent', 'Computation']

    if event_class not in allowed_classes:
        print(f"unknown event_class {event_class}. ignoring.")
        return

    input_dict = json.loads(input_json_str)
    input_dict.pop('id', None)

    filetype = input_dict.get('filetype')
    if filetype and int(filetype) != 8:
        print(f"video files must be mp4 and not debug ({input_dict.get('video_fullpath')}). ignoring.")
        return

    eventClass = globals()[event_class]

    with connection:
        session = sqlalchemy.orm.Session(connection)
        new_event = eventClass(**input_dict)

        try:
            session.add(new_event)
            session.commit()

            print(f"recorded {event_class} {new_event.id} - {new_event.event_name}")
        except sqlalchemy.exc.IntegrityError as ie:
            session.rollback()

            print(f"ignoring duplicate database entry: {ie._message} ({ie._sql_message}")       

def run_io_queues(queues = ['record_event', 'write_image']):

    with connection:
        worker = Worker(queues, connection=redis_connection())
        worker.work()
