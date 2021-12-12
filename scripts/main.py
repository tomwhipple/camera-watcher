#!/usr/bin/env python3

import json

import sqlalchemy
from sqlalchemy import text

import watcher_model
from watcher_model import EventObservation

from sshtunnel import SSHTunnelForwarder

import connect_utils
from connect_utils import TunneledConnection
from flask import *

query_uncategorized_sql = "select * from event_observations obs where obs.storage_local is True and obs.id not in (select distinct observation_id from event_classifications) order by rand() limit 20"

app = Flask("watcher")
is_cli = None

JSONIFY_PRETTYPRINT_REGULAR = True
def api_response_for_context(obj):
    if is_cli:
        return json.dumps(obj, indent=2)
    else:
        return jsonify(obj)

@app.route("/")
def hello():
    return "Hello there!\n"

@app.route("/get_uncategorized")
def get_uncategorized(request=None, context=None):
    obs_out = []

    #with connect_utils.get_ssh_tunnel() as tunnel, connect_utils.init_connection_engine(tunnel).begin() as connection:

    with TunneledConnection() as tc:

        session = sqlalchemy.orm.Session(tc)
        observations = session.query(EventObservation).from_statement(text(query_uncategorized_sql))

        for o in observations:
            obs_out.append(o.api_response_dict())

    return api_response_for_context(obs_out)


if __name__ == "__main__":
    is_cli = True
    print(get_uncategorized(None))
