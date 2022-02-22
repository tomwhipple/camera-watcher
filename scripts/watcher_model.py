import enum
import json
import random
import string

import sqlalchemy

from sqlalchemy import Column, ForeignKey, BigInteger, String, DateTime, Float, Enum, Boolean
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship

from passlib.hash import pbkdf2_sha256

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
            'video_url': BASE_URL + self.scene_name + "/capture/" + self.video_file,
            'labels': list(map(lambda : c.label, self.classifications))
        }


class EventClassification(Base):
    __tablename__ = 'event_classifications'
    id = Column(BigInteger, primary_key=True)
    observation_id = Column(BigInteger, ForeignKey('event_observations.id'))
    label = Column(String)
    decider = Column(String)
    decision_time = Column(DateTime)
    confidence = Column(Float)

    observation = relationship("EventObservation", back_populates='classifications')

    def api_response_dict(self):
        return {
            'classification_id': self.id,
            'observation_id': self.observation.id,
            'label': self.label,
            'decider': self.decider,
            'decision_time': self.decision_time.isoformat(),
            'confidence': self.confidence,
        }

class APIUser(Base):
    __tablename__ = 'api_users'
    id = Column(BigInteger, primary_key=True)
    username = Column(String(128),index = True)
    key_hash = Column(String(256))

    def reset_key(self):
        newkey = ''.join(random.choice(string.ascii_letters + string.digits) for i in range(16))
        self.key_hash = pbkdf2_sha256.hash(newkey)

        return newkey

    def verify_key(self, input_str):
        return pbkdf2_sha256.verify(input_str, self.key_hash)
