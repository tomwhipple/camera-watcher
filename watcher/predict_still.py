import logging
from pathlib import Path

import sqlalchemy
from sqlalchemy import select
from rq import Worker

from fastai.vision.all import load_learner

from .connection import TunneledConnection, application_config, redis_connection
from.model import EventObservation, EventClassification

__all__ = ['task_predict_still']

def predict_from_still(img_file: Path) -> (str, float):
    model_file = Path(__file__).parent.parent / application_config('prediction','STILL_MODEL_FILE')
    model = load_learner(model_file)

    predicted_label, i, probs = model.predict(img_file)
    probability = probs.tolist()[int(i)]
    return (predicted_label, probability)

def task_predict_still(img_file, event_name):
    img_file = Path(application_config('system','LOCAL_DATA_DIR')) / img_file

    prediction, probability = predict_from_still(img_file)
    logging.info(f"{event_name} is a {prediction} with probability {probability}")

    with TunneledConnection() as tc:
        session = sqlalchemy.orm.Session(tc)

        stmt = select(EventObservation).where(EventObservation.event_name == event_name)
        event = session.execute(stmt).scalar_one()

        newClassification = EventClassification(
            observation_id = event.id,
            label = prediction,
            confidence = probability,
            decider = 'still_model'
        )

        session.add(newClassification)
        session.commit()

def run_prediction_queue(queues = ['prediction']):
    with TunneledConnection():
        worker = Worker(queues, connection=redis_connection())
        worker.work(with_scheduler=True)
