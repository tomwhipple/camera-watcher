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


def upload_event_in_file(session, filename):
    with open(filename) as fp:
        parsed_event = json.loads(fp.readline())
        session.add(EventObservation(
            video_file=parsed_event['pathToVideo'],
            scene_name=parsed_event['instanceName'],
            capture_time=datetime.fromtimestamp(int(parsed_event['timestamp'])),
            storage_local=True
        ))

    # this causes output that can be piped to another utility, eg
    # xargs -I {} mv {} /completion_dir
    print filename

def upload_events_in_directory(session, basedir, limit):
    filelist = []

    for filename in os.listdir(basedir):
        if filename.endswith(".jsonl"):
            filelist.append(os.path.join(basedir,filename))
            if limit and len(filelist) >= limit:
                break

    for file in filelist:
        upload_event_in_file(session, file)


#def mark_local_files(session, basedir):



def main():
    parser = argparse.ArgumentParser(description='Upload events to database')
    parser.add_argument('action')
    parser.add_argument('-d', '--input_directory', type=pathlib.Path)
    parser.add_argument('-f', '--file', type=pathlib.Path)
    parser.add_argument('-l', '--limit', type=int)

    args = parser.parse_args()

    with TunneledConnection() as tc:
        session = sqlalchemy.orm.Session(tc)

        if args.action == 'upload_file':
            upload_event_in_file(session, str(args.file))
        elif args.action == 'upload_dir':
            upload_events_in_directory(session, str(args.input_directory), args.limit)
        else:
            print("No action specified.")


        session.commit()


if __name__ == "__main__":
    main()