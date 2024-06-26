#!/usr/bin/env python3

import json
import argparse
import pathlib
import requests

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
from watcher import setup_logging

from hardswitch import NetworkPowerSwitch

import api

config = application_config()
logger = setup_logging()

DEFAULT_WORKING_DIR = PurePath(config['system']['LOCAL_DATA_DIR']) or "data/video"

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



def set_user_key(session, username):
    username = username.lower()
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


def remove_night_videos(session): 
    stmt = select(EventObservation).where(EventObservation.lighting_type == "night").where(EventObservation.storage_local == True)
    result = session.execute(stmt) 

    count = 0
    for obs in result.scalars():
        if obs.file_path().is_file():
            obs.file_path().unlink()
        obs.storage_local = False

        count += 1
        if count % 100 == 0:
            session.commit()
            print(f"updated {count}")

    print(f"removed {count} files")

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

def enqueue_event(session, event_names):
    from watcher.video import task_save_significant_frame

    for name in event_names: 
        queue = Queue(connection=redis_connection(),name='event_video')
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

def uncategorized(session, limit=0):
    un = [r.api_response_dict() for r in api.fetch_uncategorized(session, limit=limit)]
    print(json.dumps(un, indent=2))

def migrate_truth(session):
    stmt = (
        select(EventObservation)
        .where(EventObservation.classifications != None)
    )
    results = session.execute(stmt)
    for evt in results.scalars():
        true_classifications = [c for c in evt.classifications if c.confidence is None]
        if len(true_classifications) == 0: continue
        
        decided_at = true_classifications[0].decision_time
        decider = true_classifications[0].decider
        labels = set()
        for c in true_classifications:
            decided_at = max(decided_at, c.decision_time)
            assert decider == c.decider
            labels.add('noise' if 'noise' in c.label else c.label)
            
        new_labeling = Labeling(
            decider = decider,
            decided_at = decided_at,
            labels = list(labels),
            event_id = evt.id
        )
        session.add(new_labeling)
        session.commit()
            

def migrate_stills(session):
    prior = {}
    stmt = (select(Computation)
            .where(Computation.success == True)
            .where(Computation.result_file != None)
            .options(sqlalchemy.orm.joinedload(Computation.event)))
    found_computations = session.execute(stmt)
    for comp in found_computations.unique().scalars():
        key = f"{comp.event.id}:{comp.result_file}"
        if prior.get(key) == None:
            prior[key] = comp
            ir = IntermediateResult.fromComputation(comp)
            session.add(ir)

    session.commit()

def main():
    parser = argparse.ArgumentParser(description='Utilites for watcher')
    parser.add_argument('action', choices=[
        'set_user',
        'update_lighting',
        'syncup',
        'enque',
        'failed',
        'ioworker',
        'videoworker',
        'predictionworker',
        'singlevideo',
        'uncategorized',
        'requeue-failed',
        'logtest',
        'migrate-labels',
        'migrate-stills',
        'pass'])
    parser.add_argument('-d', '--input_directory', type=pathlib.Path)
    parser.add_argument('-f', '--file', type=pathlib.Path)
    parser.add_argument('-l', '--limit', type=int)
    parser.add_argument('-u', '--set_user', help='generate a key for the given user, adding them if required')
    parser.add_argument('-D', '--debug', action='store_true')
    parser.add_argument('sub_args', nargs='*')

    args = parser.parse_args()

    with TunneledConnection() as tc:
        session = sqlalchemy.orm.Session(tc)

        if args.debug: 
            import pdb; pdb.set_trace()

        if args.set_user:
            set_user_key(session, str(args.set_user))
        elif args.action == 'update_lighting':
            update_solar_lighting_type(session)
        elif args.action == 'syncup':
            batch_sync_to_remote(session)
        elif args.action == 'enque':
            enqueue_event(session, args.sub_args)
        elif args.action == 'failed':
            show_failed(args.sub_args)
        elif args.action == 'ioworker':
            import watcher.lite_tasks
            watcher.lite_tasks.run_io_queues()
        elif args.action == 'videoworker':
            import watcher.video
            watcher.video.run_video_queue()
        elif args.action == 'predictionworker':
            import watcher.predict_still
            watcher.predict_still.run_prediction_queue()
        elif args.action == 'uncategorized':
            uncategorized(session, limit=args.limit)
        elif args.action == 'singlevideo':
            import watcher.video
            watcher.video.task_save_significant_frame(args.sub_args)
        elif args.action == 'logtest':
            from watcher import setup_logging
            logger = setup_logging()
            logger.fatal("This is a test of the emergency broadcast system")
            logger.info("I'm informing you")
            logger.debug("some useless details")
        elif args.action == 'migrate-labels':
            migrate_truth(session)
        elif args.action == 'migrate-stills':
            migrate_stills(session)
        else:
            print("No action specified.")

        session.commit()


if __name__ == "__main__":
    main()