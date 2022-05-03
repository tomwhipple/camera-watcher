import os

import ffmpeg
import numpy as np

import sqlalchemy
from sqlalchemy import select, desc

from .connection import TunneledConnection
from .model import EventObservation

from .image_functions import *

__all__ = ['EventVideo', 'VideoNotAvailableError']

NUM_INITAL_FRAMES_TO_AVERAGE = 5

class VideoNotAvailableError(Exception):
    def __init__(self, file):
        if not file:
            message = 'No filename given'
        else:
            message = f"{file} could not be read"

        super().__init__(message)

def fetch_video_from_file(video_file):
    if not video_file and not os.access(video_file, os.R_OK):
        raise VideoNotAvailableError(video_file)

    info = ffmpeg.probe(video_file)

    video_info = next(stream for stream in info['streams'] if stream['codec_type'] == 'video')
    width = int(video_info['width'])
    height = int (video_info['height'])
    num_frames = int(video_info['nb_frames'])

    out, err = (
        ffmpeg
        .input(video_file)
        .output('pipe:', format='rawvideo', pix_fmt='rgb24')
        .run(capture_stdout=True)
    );
    video = (
        np
        .frombuffer(out, np.uint8)
        .reshape([-1, height, width, 3])
    );

    return video

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
