import os

import ffmpeg
import numpy as np
import cv2 as cv

__all__ = ['motion_from_initial_average', 'rescale', 'threshold_video', 'apply_mask', 'fetch_video_from_file']

def fetch_video_from_file(video_file):
    info = None
    try:
        info = ffmpeg.probe(video_file)
    except Exception as e:
        print(dir(e))
        print(f"STDERR: {e.stderr}")
        print(f"STDOUT: {e.stdout}")

        raise e

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


def motion_from_initial_average(video, window_size=5):
    working = (video[window_size:,:,:,:])
    
    avg  = (np.mean(video[0:window_size,:,:,:], axis=0))
    
    return rescale(abs(working - avg)), rescale(avg), working

def rescale(f):
    if np.size(f) == 0:
        return f
    return np.uint8(((f - np.min(f))/(np.max(f) - np.min(f))) * 255)

def threshold_video(grey_frames, kern = np.ones((7,7), np.uint8)):
    thresh = np.zeros_like(grey_frames, dtype=np.uint8)
    (num_frames, height, width) = grey_frames.shape
    
    for i in range(0, num_frames):
        _, t = cv.threshold(grey_frames[i,:,:], 128, 255, cv.THRESH_BINARY)
        thresh[i,:,:] = cv.morphologyEx(t, cv.MORPH_CLOSE, kern)
        
    return thresh

def apply_mask(color_vid, mask_vid):    
    masked = np.zeros_like(color_vid)
    for i in range(3):
        masked[:,:,:,i] = color_vid[:,:,:,i] * (mask_vid/255)
        
    return masked