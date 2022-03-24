import enum
import json
import random
import string

import sqlalchemy

from sqlalchemy import Column, ForeignKey, BigInteger, String, DateTime, Float, Enum, Boolean
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship

from passlib.hash import pbkdf2_sha256

from pathlib import Path
from datetime import datetime

BASE_URL="https://home.tomwhipple.com/"
BASE_DIR="/data/video/"

Base = declarative_base()

class EventObservation(Base):
    __tablename__ = 'event_observations'
    id = Column(BigInteger, primary_key=True)
    video_file = Column(String)
    capture_time = Column(DateTime)
    scene_name = Column(String)

    storage_local = Column(Boolean)
    storage_gcloud = Column(Boolean)
    video_location = Column(String)

    classifications = relationship("EventClassification", back_populates='observation')

    def api_response_dict(self):
        url = BASE_URL 

        if self.video_location and self.storage_local:
            url += self.video_location.removeprefix(BASE_DIR) + '/' + self.video_file
        else:
            url += self.scene_name + "/capture/" + self.video_file

        return {
            'event_observation_id': self.id,
            'video_file': self.video_file,
            'capture_time': self.capture_time.isoformat(),
            'scene_name': self.scene_name,
            'video_url': url,
            'labels': list(map(lambda : c.label, self.classifications))
        }

    def __init__(self, input):
        self.video_file = input.get('video_file')
        video_fullpath = input.get('video_fullpath')
        if video_fullpath:
            p = Path(video_fullpath)
            self.video_file = str(p.name)
            self.video_location = str(p.parent)
        self.storage_local = True

        self.capture_time = datetime.fromisoformat(input.get('capture_time'))
        self.scene_name = input.get('scene_name')


class EventClassification(Base):
    __tablename__ = 'event_classifications'
    id = Column(BigInteger, primary_key=True)
    observation_id = Column(BigInteger, ForeignKey('event_observations.id'))
    label = Column(String)
    decider = Column(String)
    decision_time = Column(DateTime)
    confidence = Column(Float)
    is_deprecated = Column(Boolean)

    observation = relationship("EventObservation", back_populates='classifications')

    def api_response_dict(self):
        return {
            'classification_id': self.id,
            'event_observation_id': self.observation.id,
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
