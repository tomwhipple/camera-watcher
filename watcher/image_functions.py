import numpy as np
import cv2 as cv

__all__ = ['motion_from_initial_average', 'rescale', 'threshold_video', 'apply_mask']

def motion_from_initial_average(video, window_size=5):
    working = (video[window_size:,:,:,:])
    
    avg  = (np.mean(video[0:window_size,:,:,:], axis=0))
    
    return rescale(abs(working - avg)), rescale(avg), working

def rescale(f):
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