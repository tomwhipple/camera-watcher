import sqlalchemy
import pathlib
import csv
import tempfile

from sqlalchemy import select

from .connection import TunneledConnection
from .model import *

__all__ = ['get_labled_data', 'get_event_stills', 'get_event_labels', 'labled_as_csv']

shared_session = None
def get_shared_session() -> sqlalchemy.orm.Session:
    global shared_session

    if  shared_session == None:
        shared_session = sqlalchemy.orm.Session(TunneledConnection())
    return shared_session



def make_result_item(r) -> (pathlib.Path, str):
    if r[1].label.startswith('noise'):
        r[1].label = 'noise'
    return tuple([r[0].result_file_fullpath(), r[1].label])

shared_data = None
def get_labled_data() -> [(pathlib.Path, str)]:
    global shared_data
    
    if shared_data == None:
    
        session = get_shared_session()

        stmt = (select(Computation, EventClassification)
            .join(EventObservation, Computation.event_name == EventObservation.event_name)
            .join(EventClassification, EventClassification.observation_id == EventObservation.id)
            .where(EventObservation.lighting_type == 'daylight')
            .where(EventObservation.storage_local == True)
            .where(Computation.method_name == 'task_save_significant_frame')
            .where(Computation.result_file != None)
            .where(Computation.result_file_location != None)
         )

        results = session.execute(stmt)
        shared_data = map(make_result_item, results.fetchall())
    return shared_data
        

def get_event_stills(p=None):
    return map(lambda d: d[0].str(), get_labled_data())

def get_event_labels(p=None):
    return map(lambda d: d[1], get_labled_data())

def reset() -> None:
    global shared_session
    shared_data = None
    if shared_session:
        shared_session.close()
    shared_session = None

def labled_as_csv()-> pathlib.Path:
    reset()
    data = get_labled_data()
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tf:
        cw = csv.writer(tf, dialect='unix')
        for row in data:
            cw.writerow([str(row[0]), row[1]])

    return tf.name