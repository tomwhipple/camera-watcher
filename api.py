#!/usr/bin/env python3

import json

import sqlalchemy
from sqlalchemy import text, select

from flask import *
from flask_httpauth import HTTPBasicAuth
from werkzeug.exceptions import InternalServerError, BadRequest

from watcher import *

query_uncategorized_sql = "select * from event_observations obs where obs.storage_local is True and obs.lighting_type = 'daylight' and obs.id not in (select distinct observation_id from event_classifications) order by rand() limit 20"
query_dbtest_sql = "select count(*) from event_observations"

app = Flask("watcher")
auth = HTTPBasicAuth()
is_cli = None

@app.before_request
def log_request_info():
    #app.logger.debug('Headers: %s', request.headers)
    app.logger.debug('Body: %s', request.get_data())

@app.errorhandler(InternalServerError)
@app.errorhandler(BadRequest)
def log_error(e):
	app.logger.error('request URL: %s', request.url)
	app.logger.error('request body: %s', request.get_data())

	return 'server error', 500

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

		return jsonify(labels)

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

		new_motion = MotionEvent(input_dict)

		session.add(new_motion)
		session.commit()

		return jsonify(new_motion.api_response_dict()), 201

@app.route("/observations/", methods=['POST'])
@app.route("/observations", methods=['POST'])
@auth.login_required
def create_event_observation():
	if int(request.json.get('filetype')) != 8:
		import pdb; pdb.set_trace()
		return jsonify({'error': "debug movies not accepted"}), 400

	new_observation = None
	with TunneledConnection() as tc:
		session = sqlalchemy.orm.Session(tc)

		new_observation = EventObservation(request.json)

		session.add(new_observation)
		session.commit()

		return jsonify(new_observation.api_response_dict()), 201

@auth.verify_password
def verify_password(username, key):

	with TunneledConnection() as tc:
		session = sqlalchemy.orm.Session(tc)

		user = session.query(APIUser).filter_by(username = username).first()
		if not user or not user.verify_key(key):
			return False
		g.user = user
		return True

if __name__ == "__main__":
    is_cli = True
    print(test_database())
