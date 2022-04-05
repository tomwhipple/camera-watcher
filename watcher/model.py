
import sys
import os
import enum
import json
import random
import string
import configparser
import datetime

import sqlalchemy

from sqlalchemy import Column, ForeignKey, BigInteger, String, DateTime, Float, Enum, Boolean, Integer
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship

from passlib.hash import pbkdf2_sha256

from pathlib import Path
from astral import LocationInfo
from astral.sun import sun
import pytz

__all__ = ['MotionEvent', 'EventObservation', 'EventClassification', 'APIUser']

config = configparser.ConfigParser()
file = os.path.join(sys.path[0],'application.cfg')
config.read(file)

BASE_URL=config['system'].get('BASE_URL')
BASE_DIR=config['system'].get('BASE_DIR')

Base = declarative_base()

class MotionEvent(Base):
    __tablename__ = 'motion_events'
    id = Column(BigInteger, primary_key=True)

    frame = Column(BigInteger)
    x = Column(Integer)
    y = Column(Integer)
    width = Column(Integer)
    height = Column(Integer)
    pixels = Column(Integer)
    label_count = Column(Integer)

    event_name = Column(String)

    #observation = relationship("EventObservation", back_populates='motions')

    def __init__(self, dict):
        self.event_name = dict.get('event_name')

        self.frame = dict.get('frame')
        self.x = dict.get('x')
        self.y = dict.get('y')
        self.width = dict.get('width')
        self.height = dict.get('height')
        self.pixels = dict.get('pixels')
        self.label_count = dict.get('label_count')

        self.observation = dict.get('observation')

    def api_response_dict(self):
        return {
            'motion_event_id': self.id,
            'event_name': self.event_name,
            'frame': self.frame,
            'x': self.x,
            'y': self.y,
            'width:': self.width,
            'height': self.height,
            'pixels': self.pixels,
            'label_count': self.label_count }


class EventObservation(Base):
    __tablename__ = 'event_observations'
    id = Column(BigInteger, primary_key=True)
    video_file = Column(String)
    capture_time = Column(DateTime)
    scene_name = Column(String)

    storage_local = Column(Boolean)
    storage_gcloud = Column(Boolean)
    video_location = Column(String)

    event_name = Column(String)
    threshold = Column(Integer)
    noise_level = Column(Integer)

    lighting_type = Column(String)

    classifications = relationship("EventClassification", back_populates='observation')
    #motions = relationship("MotionEvent", back_populates='observation')

    def __init__(self, input):
        # we want to be sure we're not caching timezone offsets inadvertently
        camera_timezone = datetime.datetime.now().astimezone().tzinfo
        if config['location'].get('TIMEZONE'):
            camera_timezone = pytz.timezone(config['location'].get('TIMEZONE')) 
        camera_location = LocationInfo()

        self.video_file = input.get('video_file')
        video_fullpath = input.get('video_fullpath')
        if video_fullpath:
            p = Path(video_fullpath)
            self.video_file = str(p.name)
            self.video_location = str(p.parent)
        self.storage_local = True

        self.capture_time = datetime.datetime.fromisoformat(input.get('capture_time')).astimezone(camera_timezone)
        self.scene_name = input.get('scene_name')

        self.event_name = input.get('event_name')
        self.threshold = input.get('threshold')
        self.noise_level = input.get('noise_level')

        lat=config['location'].get('LATITUDE')
        lng=config['location'].get('LONGITUDE') 

        camera_location = LocationInfo(self.scene_name, None, camera_timezone, lat, lng)
        self.lighting_type = sunlight_from_time_for_location(self.capture_time, camera_location)

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

def sunlight_from_time_for_location(timestamp, location):
    lighting_type = 'midnight'
    time_occurs = prev_occurs = datetime.datetime(1970,1,1).astimezone()

    for this_lighting_type, this_time_occurs in sun(location.observer, date=timestamp).items():
        if timestamp > prev_occurs and timestamp >= this_time_occurs:
            prev_occurs = this_time_occurs
            lighting_type = this_lighting_type

    if lighting_type in ['noon', 'sunrise']:
        lighting_type = 'daylight'
    elif lighting_type in ['dawn', 'sunset']:
        lighting_type = 'twighlight'
    elif lighting_type in ['dusk', 'midnight']:
        lighting_type = 'night'    

    return lighting_type   

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
