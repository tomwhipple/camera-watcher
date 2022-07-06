#!/usr/bin/env python3

import sys
import json
import argparse
import pathlib
import os
import configparser
import requests
import logging

from datetime import datetime
from pathlib import PurePath, Path
from uuid import uuid1

import sqlalchemy
from sqlalchemy import select, text

from requests_toolbelt import MultipartEncoder

from rq import Queue
from rq.registry import FailedJobRegistry
from rq.job import Job

import pytz
from astral import LocationInfo

from watcher import *
from watcher.lite_tasks import run_io_queues
from hardswitch import NetworkPowerSwitch

config = application_config()
logger = logging.getLogger(sys.argv[0])

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

def batch_sync_to_remote(session):
    sync_url = config['remote']['SYNC_APP_URL'] + "/batch"
    sync_auth = (config['remote']['SYNC_USER'], config['remote']['SYNC_PASS'])

    logger.info(f"Beginning batch sync to {sync_url}")

    with NetworkPowerSwitch() as nps:
        batch_id = uuid1()
        multipart = {}

        for cls_str in ['EventObservation', 'Computation']:
            c = globals()[cls_str]

            objects = session.query(c).from_statement(c.sync_select()).all()
            logger.info(f"found {len(objects)} objects of type {cls_str} to upload")    

            i = 0
            for o in objects:
                multipart[f"{cls_str}_{i}"] = json.dumps(o, cls=JSONEncoder)

                if cls_str == 'Computation' and o.result_file_fullpath() is not None and o.result_file_fullpath().exists():
                    file_relpath = str(Path(o.result_file_location) / o.result_file)
                    multipart[f"img_file_{i}"] = (file_relpath, open(o.result_file_fullpath(), 'rb'), 'image/jpeg')

                u = Upload(object=o, upload_batch=batch_id)
                session.add(u)

                i += 1

        m = MultipartEncoder(fields=multipart)
        resp = requests.post(sync_url, data=m, headers={'Content-Type': m.content_type}, auth=sync_auth)

        session.query(Upload).filter(Upload.upload_batch == batch_id).update({Upload.http_status: resp.status_code})
        if resp.status_code == 401:
            msg = f"Invalid credentials for {sync_auth}"
            print(msg)
            logger.error(msg)
            session.rollback()
            return

        session.commit()
        logger.info(f"{resp.status_code} upload complete")

def enque_event(session, event_names):
    from watcher.video import task_save_significant_frame

    for name in event_names: 
        queue = Queue(connection=redis_connection())
        queue.enqueue(task_save_significant_frame,name)

def show_failed(sub_args=None):
    queue = Queue(connection=redis_connection())
    failed = FailedJobRegistry(queue=queue)

    purge_failed = (sub_args and len(sub_args) > 0 and sub_args[0] == 'purge')

    print("Failed jobs on image queue:")
    for job_id in failed.get_job_ids():
        job = Job.fetch(job_id, connection=redis_connection())
        if purge_failed:
            job.delete()
            print(f"deleted job {job_id}")
        else:
            print(job_id, job.exc_info)

def main():
    parser = argparse.ArgumentParser(description='Utilites for watcher')
    parser.add_argument('action', choices=['upload_file', 'upload_dir', 'record_kerberos', 'set_user', 'update_lighting', 'update_dirs', 'syncup','enque','failed','ioworker'])
    parser.add_argument('-d', '--input_directory', type=pathlib.Path)
    parser.add_argument('-f', '--file', type=pathlib.Path)
    parser.add_argument('-l', '--limit', type=int)
    parser.add_argument('-u', '--set_user', help='generate a key for the given user, adding them if required')
    parser.add_argument('-D', '--debug', action='store_true')
    parser.add_argument('sub_args', nargs='*')

    args = parser.parse_args()
    logger.setLevel("DEBUG")
    logger.addHandler(logging.StreamHandler(stream=sys.stdout))
    fileHandler = logging.FileHandler('watcher_util.log')
    fileHandler.setFormatter(logging.Formatter(fmt="%(asctime)s %(message)s"))
    logger.addHandler(fileHandler)

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
            record_kerberos_event(session, args.sub_args, args.input_directory)
        elif args.action == 'update_lighting':
            update_solar_lighting_type(session)
        elif args.action == 'update_dirs':
            update_video_directory(session)
        elif args.action == 'syncup':
            batch_sync_to_remote(session)
        elif args.action == 'enque':
            enque_event(session, args.sub_args)
        elif args.action == 'failed':
            show_failed(args.sub_args)
        elif args.action == 'ioworker':
            run_io_queues()
        else:
            print("No action specified.")

        session.commit()


if __name__ == "__main__":
    main()
