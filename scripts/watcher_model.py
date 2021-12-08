import enum
import json

import sqlalchemy

from sqlalchemy import Column, ForeignKey, BigInteger, String, DateTime, Float, Enum
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship



Base = declarative_base()

class EventObservation(Base):
	__tablename__ = 'event_observations'
	id = Column(BigInteger, primary_key=True)
	video_file = Column(String)
	capture_time = Column(DateTime)
	scene_name = Column(String)

	classifications = relationship("EventClassification", back_populates='observation')

	def api_response_dict(self):
		return {
			'event_observation_id': self.id,
			'video_file': self.video_file,
			'capture_time': str(self.capture_time),
			'scene_name': self.scene_name
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
			'decision_time': str(self.decision_time),
			'confidence': self.confidence
		}


