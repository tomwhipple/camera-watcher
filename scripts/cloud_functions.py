import json

import sqlalchemy
from sqlalchemy import text

import watcher_model
from watcher_model import EventObservation

query_uncategorized_sql = "select * from event_observations obs where obs.id not in (select distinct observation_id from event_classifications) limit 5"

def get_uncategorized(request):
	db = watcher_model.init_connection_engine()

	session = sqlalchemy.orm.Session(db)

	observations = session.query(EventObservation).from_statement(text(query_uncategorized_sql));

	obs_out = []
	for o in observations:
		#import pdb; pdb.set_trace()
		obs_out.append({'video_file': o.video_file, 'capture_time': str(o.capture_time)})

	return json.dumps(obs_out, indent=2)