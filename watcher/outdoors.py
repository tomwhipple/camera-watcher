
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, BigInteger, DateTime
from sqlalchemy.orm import Mapped, declarative_base

from astral.sun import sun

__all__ = ['Weather', 'sunlight_from_time_for_location']

Base = declarative_base()

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
        lighting_type = 'twilight'
    elif lighting_type in ['dusk', 'midnight']:
        lighting_type = 'night'    

    return lighting_type   
