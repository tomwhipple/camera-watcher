import os, sys
import ffmpeg
import json
import numpy as np
from ipywidgets import interact
from matplotlib import pyplot as plt
    
import sqlalchemy
from sqlalchemy import select, desc

import cv2 as cv

import watcher


def motion_from_initial_average(video, window_size=5):
    working = (video[window_size:,:,:,:])
    
    avg  = (np.mean(video[0:window_size,:,:,:], axis=0))
    
    return rescale(abs(working - avg)), rescale(avg)

def rescale(f):
    return np.uint8(((f - np.min(f))/(np.max(f) - np.min(f))) * 255)

