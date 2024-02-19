import sqlalchemy
import pathlib
import csv
import tempfile

import pandas as pd

from sqlalchemy import select

from .connection import TunneledConnection
from .model import *

__all__ = ['get_labeled_data', 'get_event_stills', 'get_event_labels', 'labeled_as_csv', 'labeled_as_dataframe']

## Designed to be called from within a Juypter notebook.

def make_result_item(r) -> (pathlib.Path, str):
    return tuple([r[0].result_file_fullpath(), r[2].all_labels_as_string()])

def get_labeled_data(session) -> [(pathlib.Path, str)]:
    stmt = (select(Computation, EventClassification, EventObservation)
        .join(EventObservation, Computation.event_name == EventObservation.event_name)
        .join(EventClassification, EventClassification.observation_id == EventObservation.id)
        .where(EventClassification.confidence == None) # human labelers don't set a confidence
        .where(EventObservation.storage_local == True)
        .where(Computation.method_name == 'task_save_significant_frame')
        .where(Computation.result_file != None)
        .where(Computation.result_file_location != None)
        )

    results = session.execute(stmt)
    return [tuple([r[0].result_file_fullpath(), r[2].all_labels_as_string()]) for r in results.fetchall()]
    
def get_event_stills(p=None):
    return map(lambda d: d[0].str(), get_labeled_data())

def get_event_labels(p=None):
    return map(lambda d: d[1], get_labeled_data())

def labeled_as_csv()-> pathlib.Path:
    with TunneledConnection() as tc:
        session = sqlalchemy.orm.Session(tc)
        data = get_labeled_data(session)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tf:
            cw = csv.writer(tf, dialect='unix')
            for row in data:
                cw.writerow([str(row[0]), row[1]])

        return tf.name


# TODO: doesn't quite work yet... mismatch between formatting here and what fast.ai expects
def labeled_as_dataframe() -> pd.DataFrame:
    with TunneledConnection() as tc:
        session = sqlalchemy.orm.Session(tc)
        found = get_labeled_data(session)

        records = []
        for r in found:
            df = records.append({
                # 'event_name': r[0].event_name,
                'label': r[0].all_labels_as_string(),
                'imagefile': r[1].result_file_fullpath(),
            })
        return pd.DataFrame.from_records(records)