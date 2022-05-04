import os
from pathlib import Path

import numpy as np
import imageio

import sqlalchemy
from sqlalchemy import select, desc

from .connection import TunneledConnection
from .model import EventObservation

from .image_functions import *

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

            self.file = self.event.file_path()

        self.frames = fetch_video_from_file(self.file)

    def most_significant_frame(self):
        if not self.most_significant_frame_idx:
            # working = (video[NUM_INITAL_FRAMES_TO_AVERAGE:,:,:,:])
            avg = (np.mean(self.frames[0:NUM_INITAL_FRAMES_TO_AVERAGE,:,:,:], axis=0))
            L1_dist = abs(self.frames - avg)
            norms = rescale(np.linalg.norm(L1_dist, axis=-1))
            thresh = threshold_video(norms)
            thresh_sums = np.sum(thresh, axis=(1,2))
            self.most_significant_frame_idx = np.argmax(thresh_sums)


        return self.most_significant_frame_idx

def task_save_significant_frame(names):
    name = names[0]

    vid = EventVideo(name=name)
    print(f"starting video analysis for {name}")
    f = vid.most_significant_frame()
    img_path = str(Path(vid.file).parent / f"{name}_sf.jpg")
    img = vid.frames[f,:,:,:]

    imageio.imsave(img_path, img)
    print(f"wrote {img_path}")



