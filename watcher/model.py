
import json
import platform
import time
import subprocess

from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, BigInteger, String, DateTime, Float, Boolean, Integer, text, select
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship

from pathlib import Path
from astral import LocationInfo
import pytz

from .output import get_local_time_iso
from .connection import application_config, in_docker
from .outdoors import sunlight_from_time_for_location

__all__ = ['EventObservation', 'EventClassification', 'Computation', 'LoadEventObservation', 'UniqueClassificationLabels']

config = application_config()
Base = declarative_base()

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
        self.success = False
        self.computed_at = datetime.now(timezone.utc)

        self.__dict__.update(kwargs)

        self.host_info = kwargs.get('host_info',json.dumps(platform.uname()))
        if not in_docker():
            try:
                self.git_version = kwargs.get('git_version',subprocess.check_output('git describe --always --dirty --tags'.split()).decode('utf-8').strip())
            except subprocess.CalledProcessError:
                pass

    def start_timer(self):
        self.computed_at = datetime.now(timezone.utc)
        self.timer = time.process_time()

    def end_timer(self):
        self.elapsed_seconds = time.process_time() - self.timer

    def result_file_fullpath(self):
        if not self.result_file:
            return None
        return application_config('system','LOCAL_DAT_DIR') / self.result_file_location / self.result_file

    def sync_select():
        return text("""
select *
from computations c
where id not in (select distinct object_id from uploads where object_class = 'Computation' and http_status < 400)
order by c.computed_at desc
""")


def LoadEventObservation(session, id_or_name):
    if isinstance(id_or_name, int):
        return session.query(EventObservation).get(id_or_name)
    else:
        return session.query(EventObservation).filter_by(event_name=id_or_name).first()

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
    #computations = relationship("Computation", back_populates='observation')

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
        local_root = input.get('video_root', application_config('system', 'LOCAL_DATA_DIR'))

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

    def __str__(self):
        return self.event_name
    
    def all_labels_as_string(self):
        return ' & '.join(sorted(self.all_labels()))

    def all_labels(self): 
        #return set(map(lambda c: 'noise' if c.label.startswith('noise') else c.label, self.classifications))
        return set(['noise' if c.label.startswith('noise') else c.label for c in self.classifications])

    def boxes_for_frame(self, frame):
        boxes = []
        for m in self.motions:
            if m.frame == frame: boxes.append(m.box())
        return boxes

    def api_response_dict(self):
        return {
            'event_observation_id': self.id,
            'video_file': self.video_file,
            'capture_time': get_local_time_iso(self.capture_time),
            'scene_name': self.scene_name,
            'video_url': self.video_url(),
            'labels': list(map(lambda c: c.label, self.classifications))
        }

    def video_url(self):
        return application_config('system','BASE_STATIC_PUBLIC_URL') + '/' + self.video_location + '/' + self.video_file

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
        fullpath = Path(application_config('system','LOCAL_DATA_DIR'))
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

    def __init__(self, **input):
        self.__dict__.update(input)
        self.decision_time = datetime.now()

    def __str__(self):
        return self.label

    def api_response_dict(self):
        return {
            'classification_id': self.id,
            'event_observation_id': self.observation.id,
            'label': self.label,
            'decider': self.decider,
            'decision_time': self.decision_time.isoformat(),
            'confidence': self.confidence,
        }

def UniqueClassificationLabels(session):
    stmt = (select(EventClassification.label).distinct()
        .where(EventClassification.is_deprecated == None)
        .where(EventClassification.confidence == None)
        .where(~EventClassification.label.contains(' & '))
    )

    results = session.execute(stmt).fetchall()
    labels = sorted(set(['noise' if r[0].startswith('noise') else r[0] for r in results]))
    return labels

