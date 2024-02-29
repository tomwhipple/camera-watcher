import logging
from pathlib import Path
from datetime import datetime

import sqlalchemy
from sqlalchemy import select
from rq import Worker

from fastai.vision.all import load_learner

from .connection import TunneledConnection, application_config, redis_connection, file_with_base_path
from.model import EventObservation, EventClassification

__all__ = ['task_predict_still']

logging.basicConfig(level=application_config('system', 'LOG_LEVEL').upper())

model = None

def lazy_load_model():
    global model

    if model:
        return model

    model_file = Path(__file__).parent.parent / application_config('prediction','STILL_MODEL_FILE')
    model = load_learner(model_file)


#def predict_from_still(img_file: str) -> tuple[str, float]:
def predict_from_still(img_file: str):
    lazy_load_model()

    predicted_label, hot, probs = model.predict(img_file)
    
    found_probs = {}
    for i, b in enumerate(hot):
        if b:
            found_probs[model.dls.vocab[i]] = probs[i].item()

    return predicted_label, found_probs

def task_predict_still(img_file, event_name):
    img_file = file_with_base_path(img_file)

    if not img_file.exists():
        raise FileNotFoundError(f"file {img_file} does not exist")

    try:
        prediction, probability = predict_from_still(img_file)
        logging.info(f"{event_name} is {prediction} with probability {probability}")

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
        logging.warning(f"ignoring duplicate prediction for {event_name}")
    except Exception as e: 
        logging.exception(f"error processing {img_file}: {e}")
        raise e

def run_prediction_queue(queues = ['prediction']):
    logging.info("running predictions with model " + application_config('prediction','STILL_MODEL_FILE'))

    worker = Worker(queues, connection=redis_connection())
    worker.work(with_scheduler=True)
