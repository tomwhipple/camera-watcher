

import os
import time
import json
import math

from pathlib import Path
from rq import Queue, Retry

import cv2 as cv
import numpy as np
from PIL import Image
import ffmpeg

import sqlalchemy
from sqlalchemy import select, desc

from .connection import TunneledConnection, redis_connection, application_config
from .model import EventObservation, Computation

from .image_functions import *
from .lite_tasks import *

__all__ = ['EventVideo','task_save_significant_frame']

NUM_INITAL_FRAMES_TO_AVERAGE = 5
DEFAULT_MAX_FRAMES_PER_CHUNK = 50

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
    duration = None

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

    def probe_file(self):
        try:
            info = ffmpeg.probe(self.file)

            video_info = next(stream for stream in info['streams'] if stream['codec_type'] == 'video')
            self.width = int(video_info['width'])
            self.height = int (video_info['height'])
            self.num_frames = int(video_info['nb_frames'])
            self.duration = float(video_info['duration'])

        except Exception as e:
            print(f"STDERR: {e.stderr}")
            print(f"STDOUT: {e.stdout}")

            raise e 

    def load_frames(self):
        if not self.frames:
            self.probe_file() 
            self.frames = fetch_video_from_file(self.file)

    def most_significant_frame(self):
        if not self.frames:
            self.load_frames()

        if not self.num_frames: 
            self.probe_file()

        if not self.most_significant_frame_idx:
            thresh_sums = []

            chunk_size = int(application_config('video', 'MAX_FRAMES_PER_CHUNK') or DEFAULT_MAX_FRAMES_PER_CHUNK)
            avg = (np.mean(self.frames[0:NUM_INITAL_FRAMES_TO_AVERAGE,:,:,:], axis=0, dtype=np.float32))

            for i in range(0, math.ceil(self.num_frames/chunk_size)):
                begin = i * chunk_size
                end = min((i+1) * chunk_size -1, self.num_frames)

                L1_dist = abs(self.frames[begin:end,:,:,:] - avg)
                norms = rescale(np.linalg.norm(L1_dist, axis=-1))
                thresh = threshold_video(norms)

                thresh_sums = np.append(thresh_sums, np.sum(thresh, axis=(1,2)))

            self.most_significant_frame_idx = np.argmax(thresh_sums)

        return int(self.most_significant_frame_idx)

kern = np.ones((7,7))

def find_background(cap, num_frames = NUM_INITAL_FRAMES_TO_AVERAGE):
    i = 1
    _, accum = cap.read()
    buf = []
    buf.append(accum)

    while cap.isOpened() and i < num_frames:
        _, frame = cap.read()
        accum += frame
        buf.append(frame)
        i += 1

    return np.median(buf, axis=0).astype(dtype=np.uint8), i

def find_sigificant_frame(video_source):

    cap = cv.VideoCapture(video_source,cv.CAP_FFMPEG)

    sig_frame_num = 0
    sig_frame_sum = 0
    sig_frame = None

    bg, f_num = find_background(cap)
    while cap.isOpened():
        capture_success, frame = cap.read()
        if not capture_success or frame is None: continue

        f_num += 1

        diff = cv.absdiff(frame, bg)
        gray_diff = cv.cvtColor(diff, cv.COLOR_BGR2GRAY)
        blurred = cv.morphologyEx(gray_diff, cv.MORPH_CLOSE, kern)

        _, thresh = cv.threshold(blurred, 128, 255, cv.THRESH_BINARY)

        s = np.sum(thresh)
        if s > sig_frame_sum:
            sig_frame_sum = s
            sig_frame_num = f_num
            sig_frame = frame

    return sig_frame_num, f_num, sig_frame

def task_save_significant_frame(name):
    if isinstance(name, list):
        name = name[0]
    
    with TunneledConnection() as tc:

        # HACK: rq does a terrible job ensuring jobs only run once. 
        result = {}
        session = sqlalchemy.orm.Session(tc)

        prior_results = session.execute(
            select(Computation).where(Computation.event_name == name)
            .where(Computation.method_name == 'task_save_significant_frame')
            .where(Computation.success == True)
        )
        if len(prior_results.scalars().all()) > 0:
            print(f"already computed task_save_significant_frame for {name}")
            return

        comp = Computation(event_name=name, method_name='task_save_significant_frame')
        try: 
            comp.start_timer()

            vid = EventVideo(name=name, session=session)

            print(f"starting video analysis for {name} at {vid.file}")

            #option 1 - frame by frame.
            #sig_frame, num_frames, frame_img = find_sigificant_frame(str(vid.file))

            #option 2 - read frames with ffmpeg, then work on them
            sig_frame = vid.most_significant_frame()
            num_frames = vid.num_frames
            frame_img = vid.frames[sig_frame,:,:,:]

            result['most_significant_frame'] = sig_frame
            result['number_of_frames'] = num_frames
            result['duration'] = vid.duration

            img_relpath = Path(vid.event.video_location) / f"{name}_f{sig_frame}.jpg"
            img = Image.fromarray(frame_img,mode='RGB')

            comp.result_file = img_relpath.name
            comp.result_file_location = img_relpath.parent
            comp.success = True

            queue = Queue('write_image', connection = redis_connection())
            queue.enqueue(task_write_image, args=(img, str(img_relpath)), retry=Retry(max=3, interval=5*60))

        except Exception as e:
            result['error'] = json.dumps(str(e))
            comp.success = False
            raise e

        finally: 
            comp.end_timer()
            comp.result = json.dumps(result, sort_keys=True)

            session.add(comp)
            session.commit()

        print(f"found frame {sig_frame} for {name}. Will store as {img_relpath}")
