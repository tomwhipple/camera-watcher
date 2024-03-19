#import logger
from pathlib import Path
from datetime import datetime

import sqlalchemy
from sqlalchemy import select
from rq import Worker

from fastai.vision.all import load_learner

from .connection import TunneledConnection, application_config, redis_connection, application_path_for 
from.model import EventObservation, EventClassification

from . import setup_logging

__all__ = ['task_predict_still']


logger = setup_logging()
model = None

def lazy_load_model():
    global model

    if model:
        return model

    model_file = Path(__file__).parent.parent / application_config('prediction','STILL_MODEL_FILE')
    model = load_learner(model_file)

def predict_from_still(img_file: str):
    lazy_load_model()

    predicted_label, hot, probs = model.predict(img_file)
    
    found_probs = {}
    for i, b in enumerate(hot):
        if b:
            found_probs[model.dls.vocab[i]] = probs[i].item()

    return predicted_label, found_probs

def task_predict_still(img_file, event_name):
    img_file = application_path_for(img_file)
    logger.debug(f"predicting {img_file} for {event_name}")

    if not img_file.exists():
        raise FileNotFoundError(f"file {img_file} does not exist")

    try:
        prediction, probability = predict_from_still(img_file)
        logger.info(f"{event_name} is {prediction} with probability {probability}")

        with TunneledConnection() as tc:
            session = sqlalchemy.orm.Session(tc)

            stmt = select(EventObservation).where(EventObservation.event_name == event_name)
            event = session.execute(stmt).scalar_one()

            now = datetime.now()

            for lbl, prob in probability.items():
                newClassification = EventClassification(
                    label = lbl,
                    confidence = prob,
                    decider = Path(application_config('prediction','STILL_MODEL_FILE')).name,
                    decided_at = now
                )
                event.classifications.append(newClassification)

            session.commit()
    except sqlalchemy.exc.IntegrityError as ie:
        logger.warning(f"ignoring duplicate prediction for {event_name}")
    except Exception as e: 
        logger.exception(f"error processing {img_file}: {e}")
        raise e

def run_prediction_queue(queues = ['prediction']):
    logger.info("running predictions with model " + application_config('prediction','STILL_MODEL_FILE'))

    worker = Worker(queues, connection=redis_connection())
    worker.work(with_scheduler=True)
