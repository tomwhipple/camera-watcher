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

# This global variable is declared with a value of `None`, instead of calling
# `init_connection_engine()` immediately, to simplify testing. In general, it
# is safe to initialize your database connection pool when your script starts
# -- there is no need to wait for the first request.
db = watcher_model.init_connection_engine()


def process_file(filename, conn):
	with open(filename) as fp:
		parsed_event = json.loads(fp.readline())
		conn.add(EventObservation(
				video_file=parsed_event['pathToVideo'],
				scene_name=parsed_event['instanceName'],
				capture_time=datetime.fromtimestamp(int(parsed_event['timestamp']))

			))

		#conn.commit()

		print(parsed_event['pathToVideo'])


def main():
	parser = argparse.ArgumentParser(description='Upload events to database')
	parser.add_argument('-d', '--input_directory', type=pathlib.Path)
	#parser.add_argument('-f', '--files' type=argparse.FileType('r'))
	parser.add_argument('-l', '--limit', type=int)
	parser.add_argument('--move_completed', action='store_true')

	args = parser.parse_args()

	filelist = []

	if args.input_directory:
		for filename in os.listdir(args.input_directory):
			if filename.endswith(".jsonl"):
				filelist.append(os.path.join(args.input_directory,filename))
				if args.limit and len(filelist) >= args.limit:
					break



#	try:
	with db.connect() as conn:
		session = sqlalchemy.orm.Session(db)
		for file in filelist:
			process_file(file, session)

			if args.move_completed:
				dest_dir = os.path.join(args.input_directory, "completed")
				os.makedirs(dest_dir,exist_ok=True)
				dest_file = os.path.join(dest_dir, os.path.basename(file))
				os.rename(file, dest_file)




#	except Exception as e:
#		print("Whooops!",file=sys.stderr)
#		print(e,file=sys.stderr)


if __name__ == "__main__":
	main()