#!/usr/bin/env python3

import json

import sqlalchemy
from sqlalchemy import text, select

import watcher_model
from watcher_model import *

from sshtunnel import SSHTunnelForwarder

import connect_utils
from connect_utils import TunneledConnection
from flask import *

from flask_httpauth import HTTPBasicAuth

query_uncategorized_sql = "select * from event_observations obs where obs.storage_local is True and obs.id not in (select distinct observation_id from event_classifications) order by rand() limit 20"
query_existing_labels_sql = "select distinct label from event_classifications order by label asc"

app = Flask("watcher")
auth = HTTPBasicAuth()
is_cli = None

def api_response_for_context(obj):
    if is_cli:
        return json.dumps(obj, indent=2)
    else:
        return jsonify(obj)

@app.route("/")
def hello():
    return "Hello. We're watching you.\n"

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

		stmt = select(EventClassification.label).distinct()
		labels = []
		for l in session.execute(stmt).fetchall():
			labels.append(l[0])

		return jsonify({'labels': labels})

@app.route("/classify", methods=['POST'])
@auth.login_required
def classify():
	with TunneledConnection() as tc:
		session = sqlalchemy.orm.Session(tc)

		newClassification = EventClassification(
				observation_id = request.json.get('observation_id'),
				label = request.json.get('label'),
				decider = g.user.username
			)

		session.add(newClassification)
		session.commit()

		return jsonify(newClassification.api_response_dict()), 201


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
    print(get_uncategorized(None))
