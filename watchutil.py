#!/usr/bin/env python3

import sys
import json
import argparse
import pathlib
import os
import configparser
import requests

from datetime import datetime
from pathlib import PurePath, Path

import sqlalchemy
from sqlalchemy import select, text

import pytz
from astral import LocationInfo

from watcher import *
from hardswitch import NetworkPowerSwitch

config = application_config()

DEFAULT_WORKING_DIR = PurePath(config['system']['BASE_DIR']) / 'wellerDriveway/capture'

query_get_not_uploaded = """
select *
from event_observations eo
where id not in (select distinct event_id from uploads)
order by eo.capture_time desc
"""

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
        obs.lighting_type = watcher.model.sunlight_from_time_for_location(time_with_zone,camera_location)

        count += 1
        if count % 100 == 0:
            session.commit()

            print(f"updated {count}")

    print(f"updated {count} records")

def update_video_directory(session):
    basedir = Path(config['system']['BASE_DIR'])

    stmt = select(EventObservation).where(EventObservation.video_location == None)
    result = session.execute(stmt)

    count = 0
    for obs in result.scalars():
        location = basedir / obs.scene_name / 'capture'
        videopath = location / obs.video_file
        if videopath.is_file():
            obs.video_location = location
            obs.storage_local = True

            count += 1
            if count % 100:
                session.commit()
                print(f"updated {count}")
        else:
            obs.storage_local = False

    print(f"upated {count} total file locations")

def sync_to_remote(session):

    observations = session.query(EventObservation).from_statement(text(query_get_not_uploaded)).all()
    if len(observations) == 0:
        print("Nothing to upload")
        return

    sync_url = config['remote']['SYNC_APP_URL'] + "/observations"
    sync_auth = (config['remote']['SYNC_USER'], config['remote']['SYNC_PASS'])

    with NetworkPowerSwitch() as nps:
        netsession = requests.Session()
        for o in observations:
            resp = netsession.post(sync_url, json=o.upload_dict(), auth=sync_auth)
            if resp.status_code == 200 or resp.status_code == 201:
                up = Upload({'event': o, 'result_code': resp.status_code})
                session.add(up)
            elif resp.status_code == 401:
                print("Invalid credentials")
                return

def enque_event(session, event_name):
    redis_queue().enqueue(task_save_significant_frame,event_name)


def main():
    parser = argparse.ArgumentParser(description='Utilites for watcher')
    parser.add_argument('action', choices=['upload_file', 'upload_dir', 'record_kerberos', 'set_user', 'update_lighting', 'update_dirs', 'syncup','enque'])
    parser.add_argument('-d', '--input_directory', type=pathlib.Path)
    parser.add_argument('-f', '--file', type=pathlib.Path)
    parser.add_argument('-l', '--limit', type=int)
    parser.add_argument('-u', '--set_user', help='generate a key for the given user, adding them if required')
    parser.add_argument('-D', '--debug', action='store_true')
    parser.add_argument('str', nargs='*')

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
            record_kerberos_event(session, args.str, args.input_directory)
        elif args.action == 'update_lighting':
            update_solar_lighting_type(session)
        elif args.action == 'update_dirs':
            update_video_directory(session)
        elif args.action == 'syncup':
            sync_to_remote(session)
        elif args.action == 'enque':
            enque_event(session, args.str)
        else:
            print("No action specified.")

        session.commit()


if __name__ == "__main__":
    main()
