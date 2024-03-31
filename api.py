#!/usr/bin/env python3

import json
import argparse
import re
import pytz

from datetime import datetime

from flask import *
from flask_httpauth import HTTPBasicAuth
from flask_sqlalchemy import SQLAlchemy

from sqlalchemy import select, desc
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.exc import IntegrityError

from werkzeug.exceptions import InternalServerError, BadRequest
from rq import Queue
from PIL import Image

from werkzeug.middleware.proxy_fix import ProxyFix

from watcher.model import *
from watcher.connection import get_db_url, redis_connection
from watcher.remote import APIUser
from watcher.lite_tasks import task_record_event, task_write_image

from watcher import output, setup_logging, application_config

DEFAULT_API_RESPONSE_PAGE_SIZE=10

db = SQLAlchemy(model_class=DeclarativeBase)

def create_app(db_url=None, db_options={}, testing=False) -> Flask:
    
    if not db_url:
        db_url, db_options = get_db_url()
    
    app = Flask("watcher")
    app.wsgi_app = ProxyFix(app.wsgi_app)
    app.logger = setup_logging()

    app.logger.debug(f"using db url: {db_url} with options: {db_options}")
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = db_options
    app.config['TESTING'] = testing

    db.init_app(app) 
    app.is_cli = False

    auth = HTTPBasicAuth()

    @app.before_request
    def log_before():
        app.logger.debug('Headers: %s', request.headers)

    # @app.after_request
    # def log_after(response):
    #     app.logger.info(f"{response.status_code} - {request.url}")
    #     return response

    @app.errorhandler(InternalServerError)
    def log_internal_error(e):
        app.logger.debug('request body: %s', request.get_data())
        app.logger.error(e)

        return "oops", 500

    @app.errorhandler(BadRequest)
    def log_bad_request(e):
        app.logger.debug('request body: %s', request.get_data())
        app.logger.error(e)

        return e, 400

    def api_response_for_context(obj):
        if app.is_cli:
            return json.dumps(obj, indent=2)
        else:
            return jsonify(obj)

    @app.route("/")
    def hello():
        return "Hello. We're watching you.\n"

    @app.route("/dbtest")
    def test_database():
        num_observations = db.session.query(EventObservation).count()

        return {'number_of_observations': num_observations}


    @app.route("/batch", methods=['POST'])
    @auth.login_required
    def receive_batch():
        queue = Queue('record_event', connection = redis_connection())
        imgque = Queue('write_image', connection = redis_connection())

        for k in request.form.keys():
            c, __ = k.split('_')
            j = request.form[k]
            queue.enqueue(task_record_event,args=(c, j))

        for f in request.files.keys():
            file = request.files[f]
            img = Image.open(file)

            imgque.enqueue(task_write_image, args=(img, file.filename))

        return 'ACCEPTED', 202

    @app.route("/uncategorized")
    @auth.login_required
    def get_uncategorized():

        before = None
        before_str = request.args.get("before")
        if before_str:
            try:
                localtz = pytz.timezone(application_config()['location'].get('TIMEZONE'))
                before = datetime.fromisoformat(before_str).astimezone(localtz)
                app.logger.debug(f"fetching events before: {before.isoformat()}")
            except (TypeError, ValueError) as pe:
                app.logger.debug(f"skipping 'before' parameter: {pe}")

        observations = EventObservation.uncategorized(db.session, before, DEFAULT_API_RESPONSE_PAGE_SIZE)

        return api_response_for_context([o.api_response_dict for o in observations])

    @app.route("/labels")
    @auth.login_required
    def get_labels():
        return jsonify(EventClassification.UniqueLabels(db.session))

    @app.route("/classify", methods=['POST'])
    @auth.login_required
    def classify():
        user = g.get('flask_httpauth_user', None)

        evt = EventObservation.by_id(db.session, request.json.get('event_observation_id'))
        if not evt:
            return jsonify({"error": "event observation not found"}), 404
        
        new_labels = request.json.get('labels', [])

        cleaned_labels = [re.sub(r'\s','_',l.strip()).lower() for l in new_labels]
        for l in evt.labelings:
            if l.decider == user.username:
                db.session.delete(l)
        
        new_labeling = Labeling(
            labels = cleaned_labels,
            decider = user.username,
            decided_at = datetime.now(),
            event_id = evt.id
        )
        db.session.add(new_labeling)
        evt.labelings.append(new_labeling)
        db.session.commit()

        return jsonify(new_labeling.labels), 201

    @app.route("/observations/", methods=['POST'])
    @app.route("/observations", methods=['POST'])
    @auth.login_required
    def create_event_observation():
        filetype = request.json.get('filetype')
        if filetype and int(filetype) != 8:
            msg = "video files must be mp4 and not debug"
            app.logger.error(msg)
            return jsonify({'error': msg}), 400

        new_observation = EventObservation(**request.json)

        try:
            db.session.add(new_observation)
            db.session.commit()
            response_code = 201
            response_body = jsonify(new_observation.api_response_dict)

        except IntegrityError as ie:
            session.rollback()

            stmt = select(EventObservation).where(EventObservation.event_name == new_observation.event_name)
            existing_observation = db.session.execute(stmt).scalar()

            if (existing_observation.event_name == new_observation.event_name 
                    and existing_observation.video_file == new_observation.video_file
                    and existing_observation.scene_name == new_observation.scene_name ):
                response_code = 200
                response_body = jsonify(existing_observation.api_response_dict)

            else:
                response_code = 400
                msg = "Data Integrity check failed. Ensure you're not reusing file or event names"
                app.logger.error(msg)
                response_body = jsonify({"error": msg})

        return response_body, response_code

    @auth.verify_password
    def verify_password(username, key):
        username = username.lower().strip()
        key = key.strip()
        
        if app.is_cli:
            return True

        user = APIUser.lookup_verify(db.session, username, key)
        if user:
            return user
        
        app.logger.warning(f"failed login for: '{username}' with key length {len(key)}")
        return None

    return app

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='API via command line')
    parser.add_argument('action', choices=['hello','dbtest','get_uncategorized'])

    args = parser.parse_args()
    app = create_app(testing=True)
    with app.app_context():
        app.is_cli = True
        client = app.test_client()

        if args.action == 'hello':
            print(app.hello())
        elif args.action == 'dbtest':
            print(app.test_database())
        elif args.action == 'get_labels':
            print(app.get_labels())
        elif args.action == 'get_uncategorized':
            response = client.get('/uncategorized')
            print(response.data)

        else:
            print("no action specified")

