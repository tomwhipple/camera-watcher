#!/usr/bin/env python3

import sys
import json
import argparse
import pathlib
import os

from datetime import datetime
from pathlib import PurePath

import sqlalchemy
from sqlalchemy import select

import watcher_model
from watcher_model import EventObservation
from connect_utils import TunneledConnection

DEFAULT_WORKING_DIR = PurePath('/etc/opt/kerberosio/capture/')

def upload_event_in_file(session, filename):
    with open(filename) as fp:
        parsed_event = json.loads(fp.readline())
        existing = session.execute(select(EventObservation).where(EventObservation.video_file == parsed_event['pathToVideo'])).all()

        if len(existing) == 0: 
            session.add(EventObservation(
                video_file=parsed_event['pathToVideo'],
                scene_name=parsed_event['instanceName'],
                capture_time=datetime.fromtimestamp(int(parsed_event['timestamp'])),
                storage_local=True
            ))

            # this causes output that can be piped to another utility, eg
            # xargs -I{} mv {} /completion_dir
            print(filename)


def upload_events_in_directory(session, basedir, limit):
    filelist = []

    for filename in os.listdir(basedir):
        if filename.endswith(".jsonl"):
            filelist.append(os.path.join(basedir,filename))
            if limit and len(filelist) >= limit:
                break

    for file in filelist:
        upload_event_in_file(session, file)


def write_event_jsonl(parsed_event, working_directory=DEFAULT_WORKING_DIR):

    event_name = PurePath(parsed_event['pathToVideo']).stem

    event_jsonl_file = str(PurePath(working_directory).joinpath(event_name + '.jsonl'))
    with open(event_jsonl_file, 'a+') as single_event_log:
        single_event_log.write(json.dumps(parsed_event, sort_keys=True))
        single_event_log.write("\n")

    single_event_log.close()

def record_kerberos_event(session, input_json, jsonl_directory=DEFAULT_WORKING_DIR):
    parsed_event = json.loads(input_json)

    stmt = select(EventObservation).where(EventObservation.video_file)
    result = session.execute(stmt)
    if len(result.all()) == 0:
        session.add(EventObservation(
            video_file=parsed_event['pathToVideo'],
            scene_name=parsed_event['instanceName'],
            capture_time=datetime.fromtimestamp(int(parsed_event['timestamp'])),
            storage_local=True
        ))
    write_event_jsonl(parsed_event, jsonl_directory)


def main():
    parser = argparse.ArgumentParser(description='Upload events to database')
    parser.add_argument('action')
    parser.add_argument('-d', '--input_directory', type=pathlib.Path)
    parser.add_argument('-f', '--file', type=pathlib.Path)
    parser.add_argument('-l', '--limit', type=int)
    parser.add_argument('raw_json', nargs='*')

    args = parser.parse_args()

    with TunneledConnection() as tc:
        session = sqlalchemy.orm.Session(tc)

        if args.action == 'upload_file':
            upload_event_in_file(session, str(args.file))
        elif args.action == 'upload_dir':
            upload_events_in_directory(session, str(args.input_directory), args.limit)
        elif args.action == 'record_kerberos':
            record_kerberos_event(session, args.raw_json, args.input_directory)
        elif args.action == 'debug':
            import pdb; pdb.set_trace()
        else:
            print("No action specified.")


        session.commit()


if __name__ == "__main__":
    main()
