#!/usr/bin/env python3

import json

import sqlalchemy
from sqlalchemy import text

import watcher_model
from watcher_model import EventObservation

from sshtunnel import SSHTunnelForwarder

import connect_utils
from connect_utils import TunneledConnection

query_uncategorized_sql = "select * from event_observations obs where obs.id not in (select distinct observation_id from event_classifications) order by rand() limit 3"

def get_uncategorized(request):
	obs_out = []

	#with connect_utils.get_ssh_tunnel() as tunnel, connect_utils.init_connection_engine(tunnel).begin() as connection:

	with TunneledConnection() as tc:

		session = sqlalchemy.orm.Session(tc)
		observations = session.query(EventObservation).from_statement(text(query_uncategorized_sql))

		for o in observations:
			obs_out.append(o.api_response_dict())

	return json.dumps(obs_out, indent=2)


if __name__ == "__main__":
	print(get_uncategorized(None))
