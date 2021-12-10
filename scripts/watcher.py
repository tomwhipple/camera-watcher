#!/usr/bin/env python3

import sys
import json
import argparse
import pathlib
import os

from datetime import datetime

import sqlalchemy
import watcher_model
from watcher_model import EventObservation

from connect_utils import TunneledConnection


def upload_event_in_file(session, filename, move_on_completion=True):
	with open(filename) as fp:
		parsed_event = json.loads(fp.readline())
		session.add(EventObservation(
				video_file=parsed_event['pathToVideo'],
				scene_name=parsed_event['instanceName'],
				capture_time=datetime.fromtimestamp(int(parsed_event['timestamp'])),
				storage_local=True
			))
		if move_on_completion:
			basedir = os.path.dirname(filename)
			dest_dir = os.path.join(basedir, "processed_jsonl")
			os.makedirs(dest_dir,exist_ok=True)
			dest_file = os.path.join(dest_dir, os.path.basename(file))
			os.rename(file, dest_file)

		print(parsed_event['pathToVideo'])

def upload_events_in_directory(session, basedir, limit, move_on_completion=False):
	filelist = []

	for filename in os.listdir(basedir):
		if filename.endswith(".jsonl"):
			filelist.append(os.path.join(basedir,filename))
			if limit and len(filelist) >= limit:
				break

	for file in filelist:
		upload_event_in_file(session, file, move_on_completion)


#def mark_local_files(session, basedir):



def main():
	parser = argparse.ArgumentParser(description='Upload events to database')
	parser.add_argument('action')
	parser.add_argument('-d', '--input_directory', type=pathlib.Path)
	parser.add_argument('-f', '--file', type=pathlib.Path)
	parser.add_argument('-l', '--limit', type=int)
	parser.add_argument('--move_completed', action='store_true')

	args = parser.parse_args()

	with TunneledConnection() as tc:
		session = sqlalchemy.orm.Session(tc)

		if args.action == 'upload_file':
			upload_event_in_file(session, str(args.file), args.move_completed)
		elif args.action == 'upload_dir':
			upload_events_in_directory(session, str(args.input_directory), args.move_completed, args.limit)
		else:
			print("No action specified.")


		session.commit()


if __name__ == "__main__":
	main()