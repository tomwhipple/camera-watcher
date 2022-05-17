import os
import time

from pathlib import Path
from rq import Queue, Retry

import numpy as np
from PIL import Image
import ffmpeg

import sqlalchemy
from sqlalchemy import select, desc

from .connection import TunneledConnection, redis_connection, application_config
from .model import EventObservation

from .image_functions import *
from .lite_tasks import *

__all__ = ['EventVideo','task_save_significant_frame']

NUM_INITAL_FRAMES_TO_AVERAGE = 5
MAX_FRAMES_PER_CHUNK = 100

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
    num_frames = 0
    width = 0
    height = 0

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

        try:
            info = ffmpeg.probe(self.file)

            video_info = next(stream for stream in info['streams'] if stream['codec_type'] == 'video')
            self.width = int(video_info['width'])
            self.height = int (video_info['height'])
            self.num_frames = int(video_info['nb_frames'])

        except Exception as e:
            print(f"STDERR: {e.stderr}")
            print(f"STDOUT: {e.stdout}")

            raise e 

    def load_frames(self):
        self.frames = fetch_video_from_file(self.file)

    def bytes_needed(self):
        return self.num_frames * self.height * self.width * 3

    def most_significant_frame(self):
        if not self.most_significant_frame_idx:
            thresh_sums = []

            chunk_size = MAX_FRAMES_PER_CHUNK
            avg = (np.mean(self.frames[0:NUM_INITAL_FRAMES_TO_AVERAGE,:,:,:], axis=0, dtype=np.float32))

            for i in range(0, int(self.num_frames/chunk_size)):
                begin = i * chunk_size
                end = min((i+1) * chunk_size -1, self.num_frames)

                L1_dist = abs(self.frames[begin:end,:,:,:] - avg)
                norms = rescale(np.linalg.norm(L1_dist, axis=-1))
                thresh = threshold_video(norms)

                thresh_sums.append(np.sum(thresh, axis=(1,2)))

            self.most_significant_frame_idx = np.argmax(thresh_sums)

        return self.most_significant_frame_idx

def task_save_significant_frame(name):
    if isinstance(name, list):
        name = name[0]
    
    with TunneledConnection() as tc:
        session = sqlalchemy.orm.Session(tc)

        vid = EventVideo(name=name, session=session)

        print(f"VIDEO WORKER: found {vid.width} x {vid.height} color video with {vid.num_frames} frames")
        print(f"VIDEO WORKER: expect to need at least {vid.bytes_needed()/(1024 *1024)} MB")

        vid.load_frames()

        print(f"starting video analysis for {name}")
        f = vid.most_significant_frame()

        img_relpath = str(Path(vid.event.video_location) / f"{name}_f{f}.jpg")
        img = Image.fromarray(vid.frames[f,:,:,:],mode='RGB')
        print(f"found frame {f} for {name}. Will store as {img_relpath}")

        queue = Queue('write_image', connection = redis_connection())
        queue.enqueue(task_write_image, args=(img, img_relpath), retry=Retry(max=3, interval=5*60))


