#!/usr/bin/env python3

import time
import cv2 as cv
import numpy as np

from watcher import *

camera_url = 'rtsp://drive:lookSee1@192.168.0.50:88/videoMain'
vid_file = '/Users/tw/Documents/camera-watcher/examples/20220420/20220420_075143_15.mp4'
vid_url = 'https://home.tomwhipple.com/wellerDriveway/motion/2022/06/23/20220623_132100_wellerDriveway_50.mp4'


INPUT = vid_url
NUM_FRAMES_FOR_BG = 6

def find_bg(cap, num_frames = NUM_FRAMES_FOR_BG):
	i = 1
	_, accum = cap.read()
	buf = []
	buf.append(accum)

	while cap.isOpened() and i < num_frames:
		_, frame = cap.read()
		accum += frame
		buf.append(frame)
		i += 1

	mean = accum / i

	return np.median(buf, axis=0).astype(dtype=np.uint8), i

def is_overlap(b1, b2):
	if b1 is None or b2 is None: return False

	x1, y1, w1, h1 = b1
	x2, y2, w2, h2 = b2

	return ( x1 <= x2 <= x1+w1 
		and ( y1 <= y2 <= y1+h1 
			or y1 <= y2+h2 <= y1+h2 
			or y2 <= y1 <= y2+h2
			or y2 <= y1+h1 <= y2+h2))

def merge_overlapping(b1, b2):
	x1, y1, w1, h1 = b1
	x2, y2, w2, h2 = b2

	xr = min(x1, x2)
	yr = min(y1, y2)

	wr = max(x1+w1, x2+w2) - xr
	hr = max(y1+h1, y2+h2) - yr

def merge_boxes(boxes):
	if len(boxes) <= 1:
		return boxes

	boxes = sorted(boxes, key=lambda b: b[0])

	merged = []
	while len(boxes) > 0:
		b = boxes.pop(0)
		i = 0
		while i < len(boxes):
			b2 = boxes[i]
			if is_overlap(b, b2):
				b = merge_overlapping(b, b2)
				i = 0
			else:
				i+=1
		merged.append(b)
	return merged

kern = np.ones((7,7))

cap = cv.VideoCapture(INPUT)

bg, nframes = find_bg(cap, NUM_FRAMES_FOR_BG)

# import pdb; pdb.set_trace()

ring_buf = []
bg_since = time.time()
while cap.isOpened() and cv.waitKey(30) < 0:
	_, frame = cap.read()

	if frame is None: continue

	ring_buf.append(frame)
	display = frame.copy()

	diff = cv.absdiff(frame, bg)
	gray_diff = cv.cvtColor(diff, cv.COLOR_BGR2GRAY)
	# blurred = cv.GaussianBlur(gray_diff, (11,11), 0)
	blurred = cv.morphologyEx(gray_diff, cv.MORPH_CLOSE, kern)

	_, thresh = cv.threshold(blurred, 128, 255, cv.THRESH_BINARY)

	# conturs, _ = cv.findContours(thresh, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
	conturs, _ = cv.findContours(thresh, cv.RETR_LIST, cv.CHAIN_APPROX_NONE)

	num_valid = 0
	boxes = []
	for c in conturs:
		x,y,w,h = cv.boundingRect(c)
		if w*h < 25: continue
		if y < 20: continue

		boxes.append([x,y,w,h])
		cv.rectangle(display, (x,y), (x+w, y+h),(0,255,0),1)

	boxes = merge_boxes(boxes)
	for b in boxes:
		if b is None: continue
		x,y,w,h = b
		cv.rectangle(display, (x,y), (x+w, y+h),(0,255,0),1)



	if num_valid > 10 or time.time() - bg_since > 30:
		bg = np.median(ring_buf, axis=0).astype(dtype=np.uint8)
		bg_since = time.time()

	cv.imshow('camera', display)
	# cv.imshow('threshold', blurred)

	if len(ring_buf) > NUM_FRAMES_FOR_BG:
		ring_buf.pop(0)


