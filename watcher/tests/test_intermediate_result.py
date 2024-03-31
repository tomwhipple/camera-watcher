import unittest
import os

from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from watcher.connection import application_path_for
from watcher.model import WatcherBase, IntermediateResult, EventObservation
from watcher.tests.utils import setup_test_db

class TestIntermediateResult(unittest.TestCase):
    def setUp(self):
        os.unlink('test.sqlite3')
        engine = create_engine('sqlite:///test.sqlite3', echo=False)
        #self.session, _ = setup_test_db(engine)
        self.session = sessionmaker(bind=engine)()
        
        WatcherBase.metadata.create_all(engine)

    def tearDown(self):
        self.session.close()

    def test_intermediate_result(self):
        evt = EventObservation(
            event_name='event1',
            capture_time='2021-01-01T12:00:00',
            scene_name='scene1',
            storage_local=True,
            video_location='/path/to/video',
            video_file='video1.mp4',
            threshold=10,
            noise_level=5,
        )
        self.session.add(evt)

        now = datetime.now()
        intermediate_result = IntermediateResult(
            computed_at=now,
            step='some_step',
            info={'key1': 'value1', 'key2': 'value2'},
            file='path/to/image.jpg',
            event=evt
        )
        self.session.add(intermediate_result)
        self.session.commit()

        rtr_evt = EventObservation.by_name(self.session, 'event1')
        self.assertEqual(len(rtr_evt.results), 1)
        rtr_rslt = rtr_evt.results[0]
        
        self.assertEqual(rtr_rslt.computed_at, now)
        self.assertEqual(rtr_rslt.step, 'some_step')
        self.assertEqual(rtr_rslt.info, {'key1': 'value1', 'key2': 'value2'})
        self.assertEqual(rtr_rslt.file, 'path/to/image.jpg')
        self.assertEqual(rtr_rslt.event.id, evt.id)
        
        self.assertEqual(rtr_rslt.absolute_path, application_path_for('path/to/image.jpg'))
        
        self.assertEqual(rtr_evt.significant_frame_file, application_path_for('path/to/image.jpg'))

    def test_recent(self):
        evt = EventObservation(
            event_name='event1',
            scene_name='scene1',
            video_location='/path/to/video',
            video_file='video1.mp4',
        )
        self.session.add(evt)

        ir1 = IntermediateResult(
            step='some_step',
            info={'key1': 'value1', 'key2': 'value2'},
            file='path/to/image.jpg',
            event=evt
        )
        self.session.add(ir1)

        ir2 = IntermediateResult(
            step='some_step',
            info={'key1': 'value1', 'key2': 'value2'},
            file='path/to/image2.png',
            event=evt
        )
        self.session.add(ir2)
        self.session.commit()

        rtr = IntermediateResult.recent(self.session, limit=10)
        self.assertEqual(len(rtr), 2)
    
    
                         
if __name__ == '__main__':
    unittest.main()