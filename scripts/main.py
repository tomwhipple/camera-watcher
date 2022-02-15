#!/usr/bin/env python3

import json

import sqlalchemy
from sqlalchemy import text

import watcher_model
from watcher_model import EventObservation
from watcher_model import APIUser

from sshtunnel import SSHTunnelForwarder

import connect_utils
from connect_utils import TunneledConnection
from flask import *

from flask_httpauth import HTTPBasicAuth

query_uncategorized_sql = "select * from event_observations obs where obs.storage_local is True and obs.id not in (select distinct observation_id from event_classifications) order by rand() limit 20"

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

@app.route("/get_uncategorized")
@auth.login_required
def get_uncategorized(request=None, context=None):
    obs_out = []

    with TunneledConnection() as tc:

        session = sqlalchemy.orm.Session(tc)
        observations = session.query(EventObservation).from_statement(text(query_uncategorized_sql))

        for o in observations:
            obs_out.append(o.api_response_dict())

    return api_response_for_context(obs_out)

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
    print(hello())
