import json
import sqlalchemy
from pathlib import Path
from PIL import Image

from .connection import application_config, TunneledConnection
from .model import *

__all__ = ['task_write_image','task_record_event']

def task_write_image(img, img_relpath):
    basedir = Path(application_config('system','BASE_DIR'))
    fullpath = str(basedir / img_relpath)
    img.save(fullpath, quality=85)
    print(f"wrote {fullpath}")

def task_record_event(event_class, input_json_str):
    allowed_classes = ['EventObservation', 'MotionEvent']

    if event_class not in allowed_classes:
        print(f"unknown event_class {event_class}. ignoring.")
        return

    input_dict = json.loads(input_json_str)

    filetype = input_dict.get('filetype')
    if filetype and int(filetype) != 8:
        print(f"video files must be mp4 and not debug ({input_dict.get('video_fullpath')}). ignoring.")
        return

    eventClass = globals()[event_class]

    with TunneledConnection() as tc:
        session = sqlalchemy.orm.Session(tc)
        
        new_event = eventClass(input_dict)
        session.add(new_event)
        session.commit()

        print(f"recorded {event_class} {new_event.id} - {new_event.event_name}")