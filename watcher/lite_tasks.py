import json
import sqlalchemy
import requests

from sqlalchemy import select
from pathlib import Path
from PIL import Image
from datetime import datetime, timedelta


from rq import Connection, Worker

from .connection import application_config, TunneledConnection, redis_connection
from .model import *

__all__ = ['task_write_image','task_record_event', 'run_io_queues']

weather_window = timedelta(minutes=15)

connection = TunneledConnection()

def task_write_image(img, img_relpath):
    basedir = Path(application_config('system','BASE_DIR'))
    fullpath = basedir / img_relpath

    fullpath.parent.mkdir(parents=True, exist_ok=True)

    img.save(str(fullpath), quality=85)
    print(f"wrote {fullpath}")

def task_record_event(event_class, input_json_str):
    global connection

    allowed_classes = ['EventObservation', 'MotionEvent', 'Computation']

    if event_class not in allowed_classes:
        print(f"unknown event_class {event_class}. ignoring.")
        return

    input_dict = json.loads(input_json_str)
    input_dict.pop('id', None)

    filetype = input_dict.get('filetype')
    if filetype and int(filetype) != 8:
        print(f"video files must be mp4 and not debug ({input_dict.get('video_fullpath')}). ignoring.")
        return

    eventClass = globals()[event_class]

    with connection:
        session = sqlalchemy.orm.Session(connection)
        new_event = eventClass(**input_dict)

        try:
            session.add(new_event)
            session.commit()

            print(f"recorded {event_class} {new_event.id} - {new_event.event_name}")

            if event_class == 'EventObservation' and new_event.weather_id == None:
                set_weather_for_event(new_event)

        except sqlalchemy.exc.IntegrityError as ie:
            session.rollback()

            print(f"ignoring duplicate database entry: {ie._message} ({ie._sql_message}")       

def fetch_weather():
    key = application_config('weather','API_KEY')
    lat = application_config('location','LATITUDE')
    lng = application_config('location','LONGITUDE')

    url = f"https://api.openweathermap.org/data/2.5/weather?appid={key}&lat={lat}&lon={lng}&units=metric"
    
    resp = requests.get(url)
    if resp.status_code >= 300:
        raise f"FetchWeatherError: {url} returned {resp.status_code}: {resp.text}"

    return Weather(**(resp.json()))

def set_weather_for_event(event):
    with connection:
        session = sqlalchemy.orm.Session(connection)
        # event = session.scalars(select(EventObservation).where(EventObservation.event_name == event_name)).one()
        earliest_weather = event.capture_time - weather_window
        latest_weather = event.capture_time + weather_window
        weather = session.scalars(select(Weather).where(Weather.valid_at >= earliest_weather).limit(1)).one_or_none()

        breakpoint()

        if not weather:
            weather = fetch_weather() 

            if weather and (weather.valid_at < earliest_weather or weather.valid_at > latest_weather):
                print(f"got weather for {weather.valid_at.isoformat()} but event was at {event.capture_time.isoformat()}")
                session.rollback()
                return 
            
            session.add(weather)
            session.commit()

        event.weather_id = weather.id
        session.commit()

        return 


# def test_fetch_weather():
#     key = application_config('weather','API_KEY')
#     assert key != None
#     assert len(key) > 0

#     w = fetch_weather()
#     assert w.description != None

def test_find_weather_for_event():
    example_event_name = ""
    with connection:
        session = sqlalchemy.orm.Session(connection)
        examp = session.scalars(select(EventObservation).order_by(-EventObservation.capture_time).limit(1)).one()

    example_event_name = examp.event_name

    print(f"using event {example_event_name} from {datetime.now() - examp.capture_time} ago")
    set_weather_for_event(examp)

    with connection:
        session = sqlalchemy.orm.Session(connection)
        event = session.scalars(select(EventObservation).where(EventObservation.event_name == example_event_name)).one() 
        
        if datetime.now() - event.capture_time <= weather_window:
            assert event.weather_id != None


def run_io_queues(queues = ['record_event', 'write_image']):

    with connection:
        worker = Worker(queues, connection=redis_connection())
        worker.work()
