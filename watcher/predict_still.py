from pathlib import Path
from datetime import datetime

import sqlalchemy
from rq import Worker

from fastai.vision.learner import load_learner

from .connection import TunneledConnection, application_config, redis_connection, application_path_for 
from.model import EventObservation, EventClassification, Labeling

from . import setup_logging

__all__ = ['task_predict_still']

logger = setup_logging()
model = None
model_name = None

def lazy_load_model():
    global model

    if model:
        return model, model_name

    model_file = Path(__file__).parent.parent / application_config('prediction','STILL_MODEL_FILE')
    model = load_learner(model_file)
    model_name = model_file.name
    return model, model_name

def predict_labeling(img_file: str):
    model, decider = lazy_load_model()

    labels, mask, probs = model.predict(img_file)
    
    return Labeling(
        labels = labels.items,
        decider = decider,
        decided_at = datetime.now(),
        mask = mask.tolist(),
        probabilities = probs.tolist(),
        # vocabulary = model.dls.vocab
    )

def task_predict_still(img_file, event_name):
    img_file = application_path_for(img_file)
    logger.debug(f"predicting {img_file} for {event_name}")

    if not img_file.exists():
        raise FileNotFoundError(f"file {img_file} does not exist")

    try:
        # prediction, probability = predict_from_still(img_file)
        lbl = predict_labeling(img_file)
        logger.info(f"{event_name} is {lbl}")

        with TunneledConnection() as tc:
            session = sqlalchemy.orm.Session(tc)

            event = EventObservation.by_name(session, event_name)
            lbl.event = event
            session.add(lbl)

            logger.debug(f"event id: {event.id}")

            session.commit()
    except sqlalchemy.exc.IntegrityError as ie:
        logger.warning(f"ignoring duplicate prediction for {event_name}")
    except Exception as e: 
        logger.exception(f"error predicting {img_file}: {e}")
        raise e

def run_prediction_queue(queues = ['prediction']):
    logger.info("running predictions with model " + application_config('prediction','STILL_MODEL_FILE'))

    worker = Worker(queues, connection=redis_connection())
    worker.work(with_scheduler=True)
