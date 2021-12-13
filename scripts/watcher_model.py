import enum
import json

import sqlalchemy

from sqlalchemy import Column, ForeignKey, BigInteger, String, DateTime, Float, Enum, Boolean
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship

#BASE_URL="http://raspberrypi4.local/"
BASE_URL="https://home.tomwhipple.com/"

Base = declarative_base()

class EventObservation(Base):
    __tablename__ = 'event_observations'
    id = Column(BigInteger, primary_key=True)
    video_file = Column(String)
    capture_time = Column(DateTime)
    scene_name = Column(String)

    storage_local = Column(Boolean)
    storage_gcloud = Column(Boolean)

    classifications = relationship("EventClassification", back_populates='observation')

    def api_response_dict(self):
        return {
            'event_observation_id': self.id,
            'video_file': self.video_file,
            'capture_time': self.capture_time.isoformat(),
            'scene_name': self.scene_name,
            'video_url': BASE_URL + self.scene_name + "/capture/" + self.video_file
        }


class Usefullness(enum.Enum):
    INTERESTING = 1
    BACKGROUND = 2

class EventClassification(Base):
    __tablename__ = 'event_classifications'
    id = Column(BigInteger, primary_key=True)
    observation_id = Column(BigInteger, ForeignKey('event_observations.id'))
    usefullness = Column(Enum(Usefullness))
    decider = Column(String)
    decision_time = Column(DateTime)
    confidence = Column(Float)

    observation = relationship("EventObservation", back_populates='classifications')

    def api_response_dict(self):
        return {
            'event_classification_id': self.id,
            'usefullness': str(self.usefullness),
            'decider': self.decider,
            'decision_time': self.decision_time.isoformat(),
            'confidence': self.confidence,
        }


