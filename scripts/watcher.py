#!/usr/bin/env python3

import sys
import json
import argparse
import pathlib
import os
import configparser

from datetime import datetime
from pathlib import PurePath

import sqlalchemy
from sqlalchemy import select

import watcher_model
from watcher_model import EventObservation, APIUser, sunlight_from_time_for_location
from connect_utils import TunneledConnection

import pytz
from astral import LocationInfo

config = configparser.ConfigParser()
file = os.path.join(sys.path[0],'application.cfg')
config.read(file)

DEFAULT_WORKING_DIR = PurePath('//Volumes/Video Captures/wellerDriveway/capture')



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

    counter = 0
    for file in filelist:
        upload_event_in_file(session, file)

        if counter % 25 == 0:
            session.commit()

        counter += 1


def write_event_jsonl(parsed_event, working_directory=DEFAULT_WORKING_DIR):

    event_name = PurePath(parsed_event['pathToVideo']).stem

    event_jsonl_file = str(PurePath(working_directory).joinpath(event_name + '.jsonl'))
    with open(event_jsonl_file, 'a+') as single_event_log:
        single_event_log.write(json.dumps(parsed_event, sort_keys=True))
        single_event_log.write("\n")

    single_event_log.close()

def record_kerberos_event(session, input_json, jsonl_directory=DEFAULT_WORKING_DIR):
    if isinstance(input_json, dict):
        parsed_event = input_json
    else:
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

def set_user_key(session, username):
    user = session.query(APIUser).filter_by(username = username).first()
    if not user:
        user = APIUser(username = username)
        session.add(user)

    newkey = user.reset_key()
    session.commit()

    print(f"key for {username} is now {newkey}")
    return newkey

def update_solar_lighting_type(session):
    camera_timezone = datetime.now().astimezone().tzinfo
    if config['location'].get('TIMEZONE'):
        camera_timezone = pytz.timezone(config['location'].get('TIMEZONE')) 

    lat=config['location'].get('LATITUDE')
    lng=config['location'].get('LONGITUDE') 

    camera_location = LocationInfo(None, None, camera_timezone, lat, lng)

    stmt = select(EventObservation).where(EventObservation.lighting_type == None)
    result = session.execute(stmt)

    count = 0
    for obs in result.scalars():
        time_with_zone = obs.capture_time.astimezone(camera_location.timezone)
        obs.lighting_type = sunlight_from_time_for_location(time_with_zone,camera_location)

        count += 1
        if count % 25 == 0:
            session.commit()

            print(f"updated {count}")

    print(f"updated {count} records")


def main():
    parser = argparse.ArgumentParser(description='Upload events to database')
    parser.add_argument('action', choices=['upload_file', 'upload_dir', 'record_kerberos', 'set_user', 'update_lighting'])
    parser.add_argument('-d', '--input_directory', type=pathlib.Path)
    parser.add_argument('-f', '--file', type=pathlib.Path)
    parser.add_argument('-l', '--limit', type=int)
    parser.add_argument('-u', '--set_user', help='generate a key for the given user, adding them if required')
    parser.add_argument('-D', '--debug', action='store_true')
    parser.add_argument('raw_json', nargs='*')

    args = parser.parse_args()

    with TunneledConnection() as tc:
        session = sqlalchemy.orm.Session(tc)

        if args.debug: 
            import pdb; pdb.set_trace()

        if args.set_user:
            set_user_key(session, str(args.set_user))
        elif args.action == 'upload_file':
            upload_event_in_file(session, str(args.file))
        elif args.action == 'upload_dir':
            upload_events_in_directory(session, str(args.input_directory), args.limit)
        elif args.action == 'record_kerberos':
            record_kerberos_event(session, args.raw_json, args.input_directory)
        elif args.action == 'update_lighting':
            update_solar_lighting_type(session)
        else:
            print("No action specified.")


        session.commit()


if __name__ == "__main__":
    main()
