from datetime import datetime
import os
import time
import math

from pathlib import Path
from rq import Queue, Retry, Worker

import cv2 as cv
import numpy as np
from PIL import Image
import ffmpeg

import sqlalchemy
from sqlalchemy import select

from .connection import TunneledConnection, redis_connection, application_config
from .model import EventObservation, IntermediateResult

from .image_functions import *
from .lite_tasks import *

__all__ = ['EventVideo','task_save_significant_frame', 'run_video_queue']

NUM_INITAL_FRAMES_TO_AVERAGE = 5
DEFAULT_MAX_FRAMES_PER_CHUNK = 50

from . import setup_logging
logger = setup_logging()

shared_tunnel = None
def get_shared_tunnel():
    global shared_tunnel

    if not shared_tunnel:
        shared_tunnel = TunneledConnection().connect()
    return shared_tunnel

class FFMPEGError(Exception):
    pass 

class EventVideo(object):
    tunnel = None
    session = None

    event = None
    name = None
    file = ""

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
    
    def __init__(self, session=None, name=None):
        self.session = session
        self.name = name

        stmt = select(EventObservation).where(EventObservation.event_name == self.name)
        session = self.get_session()
        self.event = session.execute(stmt).scalar()
        if not self.event:
            msg = f'event {self.name} not found'
            raise Exception(msg)

        vidfile = self.event.file_path

        if not vidfile or not os.access(vidfile, os.R_OK):
            msg = f'could not read: {vidfile}'
            raise Exception(msg)

        self.file = vidfile


    def probe_file(self):
        try:
            info = ffmpeg.probe(self.event.file_path)

            tries_remaining = 3
            while not 'streams' in info and tries_remaining > 0:
                time.sleep(1)
                info = ffmpeg.probe(self.file)
                tries_remaining -= 1

            video_info = next(stream for stream in info['streams'] if stream['codec_type'] == 'video')
            self.width = int(video_info['width'])
            self.height = int (video_info['height'])
            self.num_frames = int(video_info['nb_frames'])
            self.duration = float(video_info['duration'])

        except KeyError as ke:
            logger.error(str(ke))
            raise ke

        except Exception as e:
            logger.error(f"{str(e)} exception from ffmpeg:\nSTDERR: {e.stderr}\nSTDOUT: {e.stdout}")
            if e.stderr.endswith(b'Invalid data found when processing input\n'):
                raise FFMPEGError(f'Invalid data when probing {self.file}') from e
            else:
                raise e

    def load_frames(self):
        if not self.frames:
            self.probe_file() 
            self.frames = fetch_video_from_file(self.file)

    def most_significant_frame(self):
        if not self.frames:
            self.load_frames()

        self.num_frames = np.shape(self.frames)[0]

        if not self.most_significant_frame_idx:
            thresh_sums = np.zeros(self.num_frames)

            chunk_size = int(application_config('video', 'MAX_FRAMES_PER_CHUNK') or DEFAULT_MAX_FRAMES_PER_CHUNK)
            avg = (np.mean(self.frames[0:NUM_INITAL_FRAMES_TO_AVERAGE,:,:,:], axis=0, dtype=np.float32))

            for i in range(0, math.ceil(self.num_frames/chunk_size)):
                begin = i * chunk_size
                end = min((i+1) * chunk_size -1, self.num_frames)

                L1_dist = abs(self.frames[begin:end,:,:,:] - avg)
                norms = rescale(np.linalg.norm(L1_dist, axis=-1))
                thresh = threshold_video(norms)

                thresh_sums[begin:end] = np.sum(thresh, axis=(1,2))

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

# def find_sigificant_frame(video_source):

#     cap = cv.VideoCapture(video_source,cv.CAP_FFMPEG)

#     sig_frame_num = 0
#     sig_frame_sum = 0
#     sig_frame = None

#     bg, f_num = find_background(cap)
#     while cap.isOpened():
#         capture_success, frame = cap.read()
#         if not capture_success or frame is None: continue

#         f_num += 1

#         diff = cv.absdiff(frame, bg)
#         gray_diff = cv.cvtColor(diff, cv.COLOR_BGR2GRAY)
#         blurred = cv.morphologyEx(gray_diff, cv.MORPH_CLOSE, kern)

#         _, thresh = cv.threshold(blurred, 128, 255, cv.THRESH_BINARY)

#         s = np.sum(thresh)
#         if s > sig_frame_sum:
#             sig_frame_sum = s
#             sig_frame_num = f_num
#             sig_frame = frame

#     return sig_frame_num, f_num, sig_frame



def task_save_significant_frame(name):
    if isinstance(name, list):
        name = name[0]
    
    with TunneledConnection() as tc:

        session = sqlalchemy.orm.Session(tc)

        result = {}

        vid = EventVideo(name=name, session=session)

        logger.info(f"starting video analysis for {name} at {vid.file}")

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

        ir = IntermediateResult(
            computed_at = datetime.now(),
            step = 'task_save_significant_frame',
            file = str(img_relpath),
            info = result,
            event_id = vid.event.id
        )
        session.add(ir)
        session.commit()
        
        io_queue = Queue('write_image', connection=redis_connection())
        write_job = io_queue.enqueue(task_write_image, args=(img, str(img_relpath)), 
                            retry=Retry(max=3, interval=5*60))

        logger.info(f"found frame {sig_frame} for {name}. Will store as {img_relpath}")

        predict_queue = Queue('prediction', connection=redis_connection())
        job = predict_queue.enqueue('watcher.predict_still.task_predict_still', 
                                    depends_on=write_job,
                                    args=(str(img_relpath), name),
                                    retry=Retry(max=1, interval=17*60))
        logger.debug(f"enqueued prediction for {img_relpath} as {job.id}")

def run_video_queue(queues = ['event_video']):
    with TunneledConnection():
        worker = Worker(queues, connection=redis_connection())
        worker.work(with_scheduler=True)
