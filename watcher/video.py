import os
import time
import gc 

from pathlib import Path
from rq import Queue, Retry

import numpy as np
from PIL import Image

import sqlalchemy
from sqlalchemy import select, desc

from .connection import TunneledConnection, redis_connection, application_config
from .model import EventObservation

from .image_functions import *
from .lite_tasks import *

__all__ = ['EventVideo','task_save_significant_frame']

NUM_INITAL_FRAMES_TO_AVERAGE = 5

shared_tunnel = None
def get_shared_tunnel():
    if not shared_tunnel:
        shared_tunnel = TunneledConnection().connect()
    return shared_tunnel

class EventVideo(object):
    tunnel = None
    session = None

    event = None
    file = None
    name = None

    frames = None
    most_significant_frame_idx = None

    def get_tunnel(self):
        if not self.tunnel:
            self.tunnel = TunneledConnection().connect()
        return self.tunnel

    def get_session(self):
        if not self.session:
            self.session = sqlalchemy.orm.Session(self.get_tunnel())
        return self.session
    
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

        if not self.file:
            if not self.event:
                stmt = None
                if self.name:
                    stmt = select(EventObservation).where(EventObservation.event_name == self.name)
                else:
                    stmt = select(EventObservation).order_by(EventObservation.capture_time.desc()).limit(1)
                
                session = self.get_session()
                self.event = session.execute(stmt).scalar()
                if not self.event:
                    msg = f'event {self.name} not found'
                    raise Exception(msg)

            self.file = self.event.file_path()

        if not self.file or not os.access(self.file, os.R_OK):
            self.file = self.event.video_url()

        self.frames = fetch_video_from_file(self.file)

    def most_significant_frame(self):
        if not self.most_significant_frame_idx:
            avg = (np.mean(self.frames[0:NUM_INITAL_FRAMES_TO_AVERAGE,:,:,:], axis=0, dtype=np.float32))
            L1_dist = abs(self.frames - avg)
            norms = rescale(np.linalg.norm(L1_dist, axis=-1))
            thresh = threshold_video(norms)
            thresh_sums = np.sum(thresh, axis=(1,2))
            self.most_significant_frame_idx = np.argmax(thresh_sums)

        return self.most_significant_frame_idx

def task_save_significant_frame(name):
    if isinstance(name, list):
        name = name[0]
    
    with TunneledConnection() as tc:
        session = sqlalchemy.orm.Session(tc)

        vid = EventVideo(name=name, session=session)

        print(f"starting video analysis for {name}")
        f = vid.most_significant_frame()
        img_relpath = str(Path(vid.event.video_location) / f"{name}_f{f}.jpg")
        img = Image.fromarray(vid.frames[f,:,:,:],mode='RGB')

        queue = Queue('write_image', connection = redis_connection())
        queue.enqueue(task_write_image, args=(img, img_relpath), retry=Retry(max=3, interval=5*60))


