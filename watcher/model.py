
import sys
import os
import enum
import json
import random
import string
import configparser
import platform
import time
import subprocess

import sqlalchemy

from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, BigInteger, String, DateTime, Float, Enum, Boolean, Integer, text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship, Mapped, mapped_column

from passlib.hash import pbkdf2_sha256

from pathlib import Path
from astral import LocationInfo
from astral.sun import sun
import pytz

from .connection import application_config

__all__ = ['MotionEvent', 'EventObservation', 'EventClassification', 'APIUser', 'Upload', 'Computation', 'JSONEncoder', 'Weather']

config = application_config()

BASE_URL=os.environ.get('BASE_URL') or config['system'].get('BASE_URL')
BASE_DIR=os.environ.get('BASE_DIR') or config['system'].get('BASE_DIR') 

Base = declarative_base()

class JSONEncoder(json.JSONEncoder):
    def default(self, o):

        if isinstance(o, datetime):
            return o.isoformat()

        if type(o).__name__ in ['Computation', 'MotionEvent', 'EventObservation', 'EventClassification']:

            result = o.__dict__.copy()
            for k in o.__dict__.keys():
                if k[0] == '_':
                    del result[k]
                elif isinstance(result[k], datetime):
                    result[k] = result[k].isoformat()

            return result

        return json.JSONEncoder.default(self,o)

class Upload(Base):
    __tablename__ = 'uploads'
    id = Column(BigInteger, primary_key=True)
    sync_at = Column(DateTime)
    object_class = Column(String)
    object_id = Column(BigInteger)
    http_status = Column(Integer)
    upload_batch = Column(String)

    def __init__(self, **input):
        self.__dict__.update(input)
        self.sync_at = datetime.now(timezone.utc)

        event = input.get('event') or input.get('object')
        if event:
            self.object_id = event.id
            self.object_class = type(event).__name__

class Computation(Base):
    __tablename__ = 'computations'
    id = Column(BigInteger, primary_key=True)
    event_name = Column(String)
    method_name = Column(String)
    computed_at = Column(DateTime)
    elapsed_seconds = Column(Float)
    git_version = Column(String)
    host_info = Column(String)
    success = Column(Boolean)
    result = Column(String)
    result_file = Column(String)
    result_file_location = Column(String)

    timer = 0

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

        self.host_info = kwargs.get('host_info',json.dumps(platform.uname()))
        try:
            self.git_version = kwargs.get('git_version',subprocess.check_output('git describe --always --dirty --tags'.split()).decode('utf-8').strip())
        except Exception as e:
            print("Intercepted an error: ", e)

    def start_timer(self):
        self.computed_at = datetime.now(timezone.utc)
        self.timer = time.process_time()

    def end_timer(self):
        self.elapsed_seconds = time.process_time() - self.timer

    def result_file_fullpath(self):
        if not self.result_file:
            return None
        return Path(BASE_DIR) / self.result_file_location / self.result_file

    def sync_select():
        return text("""
select *
from computations c
where id not in (select distinct object_id from uploads where object_class = 'Computation' and http_status < 400)
order by c.computed_at desc
""")

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
    source = Column(String)
    source_version = Column(String)

    capture_time = None

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

    def box(self):
        return (
            int(self.x - self.width/2),
            int(self.y - self.height/2),
            self.width,
            self.height
        )


class Weather(Base):
    __tablename__ = 'weather'
    id: Mapped[int] = Column(BigInteger, primary_key=True)
    valid_at = Column(DateTime)
    valid_at_tz_offset_min = Column(Integer)
    description = Column(String) 
    temp_c = Column(Float)
    feels_like_c = Column(Float)
    temp_min_c = Column(Float)
    temp_max_c = Column(Float)
    pressure_hpa = Column(Integer)
    visibility = Column(Integer)
    humid_pct = Column(Integer)
    wind_speed = Column(Float)
    wind_dir = Column(Integer)
    cloud_pct = Column(Integer)

    def __init__(self, **input): 
        self.description = input['weather'][0].get('description')
        self.valid_at = datetime.fromtimestamp(input.get('dt'))
        self.valid_at_tz_offset_min = input.get('timezone') / 60
        self.temp_c = input['main'].get('temp')
        self.feels_like_c = input['main'].get('feels_like')
        self.temp_min_c = input['main'].get('temp_min')
        self.temp_max_c = input['main'].get('temp_max')
        self.pressure_hpa = input['main'].get('pressure')
        self.humid_pct = input['main'].get('humidity')
        self.visibility = input.get('visibility')
        self.wind_speed = input['wind'].get('speed')
        self.wind_dir = input['wind'].get('deg')
        self.cloud_pct = input['clouds'].get('all')


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
    motions = relationship("MotionEvent", 
                            foreign_keys=[event_name], 
                            primaryjoin=lambda: EventObservation.event_name == MotionEvent.event_name,
                            uselist=True, 
                            backref="observation")

    # weather = relationship("Weather", foreign_keys=[id], primaryjoin=lambda: EventObservation.weather_id == Weather.id) 
    # weather_id : Mapped[int] = mapped_column(ForeignKey("weather.id"))
    # weather: Mapped["Weather"]
    weather_id = Column(Integer)

    def __init__(self, **input):
        self.__dict__.update(input)

        # we want to be sure we're not caching timezone offsets inadvertently
        camera_timezone = datetime.now().astimezone().tzinfo
        if config['location'].get('TIMEZONE'):
            camera_timezone = pytz.timezone(config['location'].get('TIMEZONE')) 
        camera_location = LocationInfo()

        video_fullpath = input.get('video_fullpath')
        local_root = input.get('video_root', BASE_DIR)

        if video_fullpath:
            p = Path(video_fullpath)
            self.video_file = str(p.name)
            self.video_location = str(p.parent).removeprefix(local_root + '/')
        else:
            self.video_file = input.get('video_file',"")
            self.video_location = input.get('video_location',"")

        self.storage_local = self.file_path().is_file()

        timestr = input.get('capture_time', datetime.now().isoformat())
        self.capture_time = datetime.fromisoformat(timestr).astimezone(camera_timezone)
        self.scene_name = input.get('scene_name',"")
        self.event_name = input.get('event_name',"")

        lat=config['location'].get('LATITUDE')
        lng=config['location'].get('LONGITUDE') 

        camera_location = LocationInfo(self.scene_name, None, camera_timezone, lat, lng)
        self.lighting_type = input.get('lighting_type',sunlight_from_time_for_location(self.capture_time, camera_location))

    def boxes_for_frame(self, frame):
        boxes = []
        for m in self.motions:
            if m.frame == frame: boxes.append(m.box())
        return boxes

    def api_response_dict(self):
        return {
            'event_observation_id': self.id,
            'video_file': self.video_file,
            'capture_time': self.capture_time.isoformat(),
            'scene_name': self.scene_name,
            'video_url': self.video_url(),
            'labels': list(map(lambda : c.label, self.classifications))
        }

    def video_url(self):
        url = BASE_URL 

        if self.video_location and self.storage_local:
            url += self.video_location.removeprefix(BASE_DIR) + '/' + self.video_file
        else:
            url += self.scene_name + "/capture/" + self.video_file

        return url

    def upload_dict(self):
        return {
            'event_name': self.event_name,
            'video_file': self.video_file,
            'video_location': self.video_location,
            'scene_name': self.scene_name,
            'capture_time': self.capture_time.isoformat(),
            'threshold': self.threshold,
            'noise_level': self.noise_level,
            'lighting_type': self.lighting_type,
            'filetype': 8
        }

    def file_path(self):
        fullpath = Path(BASE_DIR)
        if self.video_location:
            fullpath = fullpath / self.video_location / self.video_file
        else:
            fullpath = fullpath / self.scene_name / 'capture' / self.video_file

        return fullpath

    def sync_select():
        return text("""
select *
from event_observations eo
where id not in (select distinct object_id from uploads where object_class = 'EventObservation' and http_status < 400)
order by eo.capture_time desc
""")

def sunlight_from_time_for_location(timestamp, location):
    lighting_type = 'midnight'
    time_occurs = prev_occurs = datetime(1970,1,1).astimezone()

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
