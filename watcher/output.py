import json
import pytz

from datetime import datetime

from .connection import application_config

def get_local_time_iso(a_time):
    tz = pytz.timezone(application_config('location', 'TIMEZONE')) 
    with_tz = tz.localize(a_time)
    return with_tz.isoformat()

class JSONEncoder(json.JSONEncoder):
    def default(self, o):

        if isinstance(o, datetime):
            return get_local_time_iso(o)

        if type(o).__name__ in ['Computation', 'EventObservation', 'EventClassification']:

            result = o.__dict__.copy()
            for k in o.__dict__.keys():
                if k[0] == '_':
                    del result[k]
                elif isinstance(result[k], datetime):
                    result[k] = get_local_time_iso(result[k])

            return result

        return json.JSONEncoder.default(self,o)