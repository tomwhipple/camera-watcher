import os
import sys

import enum

from sqlalchemy import Column, ForeignKey, BigInteger, String, DateTime, Float, Enum
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship

from sqlalchemy import create_engine


Base = declarative_base()

class EventObservation(Base):
	__tablename__ = 'event_observations'
	id = Column(BigInteger, primary_key=True)
	video_file = Column(String)
	capture_time = Column(DateTime)
	scene_name = Column(String)

	classifications = relationship("EventClassification", back_populates='observation')

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
