#!/usr/bin/env python3

import time
import cv2 as cv
import numpy as np
import json
import argparse

from watcher import *

NUM_FRAMES_FOR_BG = 6
BOX_MARGIN = 5

kern = np.ones((7,7))

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

def draw_boxes(base_image, boxes=[], color=(0,255,0)):
	for b in boxes:
		if b is None: continue
		x,y,w,h = b
		cv.rectangle(base_image, (x,y), (x+w, y+h),color,1)
		
	return base_image

def find_moving_objects(video_source,show_work=False):

	cap = cv.VideoCapture(video_source)

	bg, frames_since_start = find_bg(cap, NUM_FRAMES_FOR_BG)

	motion_in_progress = False
	ring_buf = []
	bg_at = time.time()

	resulting_boxes = {}

	while cap.isOpened() and cv.waitKey(30) < 0:
		capture_success, frame = cap.read()

		if not capture_success or frame is None: continue

		frames_since_start += 1
		ring_buf.append(frame)

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
			if w*h < 120: continue
			if y < 20: continue

			boxes.append([x,y,w,h])

		boxes = merge_boxes(boxes)
		resulting_boxes[frames_since_start] = boxes
		motion_in_progress = len(boxes) > 0

		time_since_bg = time.time() - bg_at
		if (not motion_in_progress and time_since_bg > 10) or time_since_bg > 45:
			bg = np.median(ring_buf, axis=0).astype(dtype=np.uint8)
			bg_at = time.time()

		if show_work:
			display = frame.copy()
			display = draw_boxes(display, boxes)

			if motion_in_progress:
				cv.putText(display, f"MOTION DETECTED: {len(boxes)}", (10, 700), cv.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)

			cv.imshow('camera', display)
			# cv.imshow('threshold', blurred)

		if len(ring_buf) > NUM_FRAMES_FOR_BG:
			ring_buf.pop(0)

	return resulting_boxes

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="find bounding boxes for motion")
	parser.add_argument('video_url')
	parser.add_argument('-S', '--silent', action='store_true')

	args = parser.parse_args()

	result = find_moving_objects(video_source=args.video_url,show_work=not args.silent)
	print(json.dumps(result, sort_keys=True))

