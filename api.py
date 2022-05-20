#!/usr/bin/env python3

import json
import argparse

import sqlalchemy
from sqlalchemy import text, select

from flask import *
from flask_httpauth import HTTPBasicAuth
from werkzeug.exceptions import InternalServerError, BadRequest
from rq import Queue, Retry

from watcher.model import *
from watcher.connection import *
from watcher.lite_tasks import task_record_event

query_uncategorized_sql = """select * 
from event_observations obs 
where obs.storage_local is True 
and obs.lighting_type = 'daylight' 
and obs.id not in (select distinct observation_id from event_classifications) order by rand() limit 20"""
query_dbtest_sql = "select count(*) from event_observations"

app = Flask("watcher")
auth = HTTPBasicAuth()
is_cli = None

@app.before_request
def log_before():
    app.logger.debug('Headers: %s', request.headers)
#    app.logger.debug('Body: %s', request.get_data())

@app.after_request
def log_after(response):
    app.logger.info(f"{response.status_code} - {request.url}")

    return response

@app.errorhandler(InternalServerError)
def log_internal_error(e):
#    app.logger.error('request body: %s', request.get_data())
    app.logger.error(e)

    return "oops", 500

@app.errorhandler(BadRequest)
def log_bad_request(e):
#    app.logger.error('request body: %s', request.get_data())
    app.logger.error(e)

    return e, 400

def api_response_for_context(obj):
    if is_cli:
        return json.dumps(obj, indent=2)
    else:
        return jsonify(obj)

@app.route("/")
def hello():
    return "Hello. We're watching you.\n"

@app.route("/dbtest")
def test_database():
    num_observations = None
    with TunneledConnection() as tc:
        session = sqlalchemy.orm.Session(tc)

        num_observations = session.query(EventObservation).count()

    return {'number_of_observations': num_observations}


@app.route("/batch", methods=['POST'])
@auth.login_required
def recieve_batch():
    queue = Queue('record_event', connection = redis_connection())

    for k in request.form.keys():
        c, __ = k.split('_')

        j = request.form[k]

        queue.enqueue(task_record_event,args=(c, j))

    return 'ACCEPTED', 202

@app.route("/uncategorized")
@auth.login_required
def get_uncategorized(request=None, context=None):
    obs_out = []

    with TunneledConnection() as tc:

        session = sqlalchemy.orm.Session(tc)
        observations = session.query(EventObservation).from_statement(text(query_uncategorized_sql))

        for o in observations:
            obs_out.append(o.api_response_dict())

    return api_response_for_context(obs_out)

@app.route("/labels")
@auth.login_required
def get_labels():
    with TunneledConnection() as tc:
        session = sqlalchemy.orm.Session(tc)

        stmt = select(EventClassification.label).distinct().where(EventClassification.is_deprecated == None)
        labels = []
        for l in session.execute(stmt).fetchall():
            labels.append(l[0])

        return json.dumps(labels)

@app.route("/classify", methods=['POST'])
@auth.login_required
def classify():
    with TunneledConnection() as tc:
        session = sqlalchemy.orm.Session(tc)

        for lbl in request.json.get('labels', []):
            newClassification = EventClassification(
                observation_id = request.json.get('event_observation_id'),
                label = lbl,
                decider = g.user.username
            )
            session.add(newClassification)

        session.commit()

        return jsonify(newClassification.api_response_dict()), 201

@app.route("/motions", methods=['POST'])
@auth.login_required
def create_motion_event():
    input_dict = request.json

    with TunneledConnection() as tc:
        session = sqlalchemy.orm.Session(tc)

        new_motion = MotionEvent(**input_dict)

        session.add(new_motion)
        session.commit()

        return jsonify(new_motion.api_response_dict()), 201

@app.route("/observations/", methods=['POST'])
@app.route("/observations", methods=['POST'])
@auth.login_required
def create_event_observation():
    filetype = request.json.get('filetype')
    if filetype and int(filetype) != 8:
        msg = "video files must be mp4 and not debug"
        app.logger.error(msg)
        return jsonify({'error': msg}), 400

    with TunneledConnection() as tc:
        session = sqlalchemy.orm.Session(tc)

        new_observation = EventObservation(**request.json)

        try:
            session.add(new_observation)
            session.commit()
            response_code = 201
            response_body = jsonify(new_observation.api_response_dict())

        except sqlalchemy.exc.IntegrityError as ie:
            session.rollback()

            stmt = select(EventObservation).where(EventObservation.event_name == new_observation.event_name)
            existing_observation = session.execute(stmt).scalar()

            if (existing_observation.event_name == new_observation.event_name 
                    and existing_observation.video_file == new_observation.video_file
                    and existing_observation.scene_name == new_observation.scene_name ):
                response_code = 200
                response_body = jsonify(existing_observation.api_response_dict())

            else:
                response_code = 400
                msg = "Data Integrity check failed. Ensure you're not reusing file or event names"
                app.logger.error(msg)
                response_body = jsonify({"error": msg})

        return response_body, response_code


@auth.verify_password
def verify_password(username, key):
    if is_cli:
        return True

    with TunneledConnection() as tc:
        session = sqlalchemy.orm.Session(tc)

        user = session.query(APIUser).filter_by(username = username).first()
        if not user or not user.verify_key(key):
            return False
        g.user = user
        return True

if __name__ == "__main__":
    is_cli = True

    parser = argparse.ArgumentParser(description='API via command line')
    parser.add_argument('action', choices=['hello','dbtest'])

    args = parser.parse_args()

    if args.action == 'hello':
        print(hello())
    elif args.action == 'dbtest':
        print(test_database())
    elif args.action == 'get_labels':
        print(get_labels())
    elif args.action == 'get_uncategorized':
        print(get_uncategorized())
    else:
        print("no action specified")

