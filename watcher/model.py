
import json
import platform
import time
import subprocess

from datetime import datetime, timezone

from typing import Optional, List
from sqlalchemy import JSON, ForeignKey, Integer, Text, text, select, desc 
from sqlalchemy.orm import relationship, mapped_column, Mapped, DeclarativeBase

from PIL import Image

from pathlib import Path
from astral import LocationInfo
import pytz

from .output import get_local_time_iso
from .connection import application_config, in_docker, application_path_for
from .outdoors import sunlight_from_time_for_location

__all__ = ['EventObservation', 'EventClassification', 'Computation', 'Labeling', 'IntermediateResult']

config = application_config()
class WatcherBase(DeclarativeBase):
    pass

class EventObservation(WatcherBase):
    __tablename__ = 'event_observations'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    event_name: Mapped[str] = mapped_column()
    video_file: Mapped[str] = mapped_column()
    capture_time: Mapped[datetime] = mapped_column()
    scene_name: Mapped[str] = mapped_column()
    storage_local: Mapped[bool] = mapped_column()
    video_location: Mapped[str] = mapped_column()
    
    threshold: Mapped[Optional[int]] = mapped_column()
    noise_level: Mapped[Optional[int]] = mapped_column()
    lighting_type: Mapped[Optional[str]] = mapped_column()

    classifications: Mapped[List['EventClassification']] = relationship(back_populates='observation', )
    computations: Mapped[List['Computation']] = relationship()

    labelings: Mapped[List['Labeling']] = relationship("Labeling", back_populates="event")
    results: Mapped[List['IntermediateResult']] = relationship("IntermediateResult", back_populates="event")
 
    @classmethod
    def uncategorized(cls, session, before: datetime=None, limit: int=1,
                      lighting = ['daylight','twilight'],
                      truth_only = True
                      ):
        #import pdb; pdb.set_trace()
        
        
        
        stmt = (
            select(cls).where(cls.labelings == None)
        )
        if before:
            stmt = stmt.where(cls.capture_time < before)
        if lighting:
            stmt = stmt.where(cls.lighting_type.in_(lighting))
            
        stmt = stmt.order_by(desc(cls.capture_time)).limit(limit)

        results = session.execute(stmt).scalars().all()
        return results

    @classmethod
    def by_name(cls, session, name):
        return session.query(cls).filter_by(event_name=name).first()
    
    @classmethod
    def by_id(cls, session, id):
        return session.get(cls, id)

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

        self.storage_local = self.file_path.is_file()

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

    def __repr__(self):
        return f"<EventObservation {self.event_name} at {self.capture_time.isoformat()}>"

    @property
    def significant_frame_file(self) -> Path:
        return application_path_for(self.results[-1].file) if len(self.results) else None

    @property
    def significant_frame(self) -> Image:
        if self.significant_frame_file and self.significant_frame_file.exists(): 
            try:
                return Image.open(self.significant_frame_file)
            except Exception as e:
                logger.error(f"Could not open image file {self.significant_frame_file}: {e}")
                pass

    @property 
    def true_labeling(self):
        for l in self.labelings:
            if not l.probabilities:
                return l.labels
        return None

    @property
    def true_labeling_as_string(self):
        if not self.true_labeling: return None
        return ' & '.join(self.true_labeling)
    
    @property
    def all_labels_as_string(self):
        return ' & '.join(sorted(self.all_labels))

    @property
    def all_labels(self): 
        if not self.labelings: return None

        labels = set()
        for l in self.labelings:
            if 'noise' in l.labels:
                labels.add('noise')
            else:
                labels.update(l.labels)
        return sorted(labels)

    @property
    def api_response_dict(self):
        return {
            'event_observation_id': self.id,
            'video_file': self.video_file,
            'capture_time': get_local_time_iso(self.capture_time),
            'scene_name': self.scene_name,
            'video_url': self.video_url,
            'labels': self.all_labels
        }

    @property
    def video_url(self):
        return application_config('system','BASE_STATIC_PUBLIC_URL') + '/' + self.video_location + '/' + self.video_file

    @property
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

    @property
    def file_path(self) -> Path:
        fullpath = Path(application_config('system','LOCAL_DATA_DIR'))
        if self.video_location:
            fullpath = fullpath / self.video_location / self.video_file
        else:
            fullpath = fullpath / self.scene_name / 'capture' / self.video_file

        return fullpath

    def _sync_select():
        return text("""
select *
from event_observations eo
where id not in (select distinct object_id from uploads where object_class = 'EventObservation' and http_status < 400)
order by eo.capture_time desc
""")


class Labeling(WatcherBase):
    __tablename__ = 'labelings'
    
    id: Mapped[int] = mapped_column(primary_key=True)  
    decider: Mapped[str] = mapped_column()
    decided_at: Mapped[datetime] = mapped_column()

    labels: Mapped[List[str]] = mapped_column(JSON)
    mask: Mapped[Optional[List[bool]]] = mapped_column(JSON)
    probabilities: Mapped[Optional[List[float]]] = mapped_column(JSON)
    
    event_id = mapped_column(ForeignKey('event_observations.id'), nullable=False)
    event: Mapped['EventObservation'] = relationship()

    def __init__(self, **input):
        super().__init__(**input)
        if not self.decided_at: self.decided_at = datetime.now()

    def __repr__(self):
        return f"<Labeling {self.labels}: {self.probabilities}>"

    @classmethod
    def UniqueLabels(cls, session):
        stmt = (select(cls.labels).distinct())
        results = session.execute(stmt).scalars()

        labels = set()
        for r in results:
            labels.update(r)

        return sorted(labels)

# deprecated
class EventClassification(WatcherBase):
    __tablename__ = 'event_classifications'

    id: Mapped[int] = mapped_column(primary_key=True)
    observation_id: Mapped[int] = mapped_column(ForeignKey('event_observations.id'))
    label: Mapped[str] = mapped_column()
    decider: Mapped[str] = mapped_column()
    decision_time: Mapped[datetime] = mapped_column()
    confidence: Mapped[Optional[float]] = mapped_column()    
    is_deprecated: Mapped[Optional[bool]] = mapped_column()

    observation: Mapped['EventObservation'] = relationship(back_populates='classifications')

    def __init__(self, **input):
        self.__dict__.update(input)
        self.decision_time = datetime.now()

    def __str__(self):
        return self.label

    def __repr__(self):
        return f"<EventClassification {self.label}: {self.confidence} by {self.decider}>"

    @property
    def api_response_dict(self):
        return {
            'classification_id': self.id,
            'event_observation_id': self.observation.id,
            'label': self.label,
            'decider': self.decider,
            'decision_time': self.decision_time.isoformat(),
            'confidence': self.confidence,
        }

    @classmethod
    def UniqueLabels(cls, session):
        stmt = (select(cls.label).distinct()
            .where(cls.is_deprecated == None)
            .where(cls.confidence == None)
            .where(~cls.label.contains(' & '))
        )

        results = session.execute(stmt).fetchall()
        labels = sorted(set(['noise' if r[0].startswith('noise') else r[0] for r in results]))
        return labels

# deprecated
class Computation(WatcherBase):
    __tablename__ = 'computations'

    id: Mapped[int] = mapped_column(primary_key=True)
    event_name: Mapped[str] = mapped_column(ForeignKey('event_observations.event_name'))
    method_name: Mapped[str] = mapped_column()
    computed_at: Mapped[datetime] = mapped_column()
    elapsed_seconds: Mapped[float] = mapped_column()
    git_version: Mapped[Optional[str]] = mapped_column(Text)
    host_info: Mapped[Optional[str]] = mapped_column(Text)
    success: Mapped[bool] = mapped_column()
    result: Mapped[Optional[str]] = mapped_column(Text)
    result_file: Mapped[Optional[str]] = mapped_column()
    result_file_location: Mapped[Optional[str]] = mapped_column()

    event = relationship('EventObservation', back_populates='computations')

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

    @property
    def result_file_fullpath(self) -> Path:
        if not self.result_file:
            return None
        return application_path_for( self.result_file_location ) / self.result_file

    def sync_select():
        return text("""
select *
from computations c
where id not in (select distinct object_id from uploads where object_class = 'Computation' and http_status < 400)
order by c.computed_at desc
""")

class IntermediateResult(WatcherBase):
    __tablename__ = 'intermediate_results'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    computed_at: Mapped[datetime] = mapped_column()
    step: Mapped[str] = mapped_column()
    info: Mapped[Optional[dict]] = mapped_column(JSON)
    file: Mapped[Optional[str]] = mapped_column(Text)
    
    event_id = mapped_column(ForeignKey('event_observations.id'), nullable=False)
    event: Mapped['EventObservation'] = relationship()

    def __init__(self, **input):
        super().__init__(**input)
        if not self.computed_at: self.computed_at = datetime.now()

    def __repr__(self):
        return f"<{self.step} result: {self.file} at {self.computed_at}>"

    @classmethod
    def fromComputation(cls, comp: Computation):
        if not comp.success:
            return None
        return cls(
            computed_at = comp.computed_at,
            step = comp.method_name,
            file = str(Path(comp.result_file_location) / comp.result_file),
            info = comp.result,
            event_id = comp.event.id
        )

    @classmethod
    def recent(cls, session, limit=1):
        stmt = (select(cls).order_by(desc(cls.computed_at)).limit(limit))
        return session.execute(stmt).scalars().all()

    @property
    def absolute_path(self):
        return application_path_for(self.file)
