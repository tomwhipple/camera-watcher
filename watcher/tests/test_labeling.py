import unittest
import os

from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from watcher.model import EventClassification, Labeling, WatcherBase, EventObservation
from watcher.tests.utils import setup_test_db

class TestLabeling(unittest.TestCase):
    def setUp(self):
        os.unlink('test.sqlite3')
        engine = create_engine('sqlite:///test.sqlite3', echo=False)
        self.session, _ = setup_test_db(engine)
        self.session = sessionmaker(bind=engine)()
        
        # WatcherBase.metadata.create_all(engine)

    def tearDown(self):
        self.session.close()

    def test_labeling(self):
        evt = EventObservation(
            event_name='event1',
            video_file='video1.mp4',
            capture_time='2021-01-01T12:00:00',
            scene_name='scene1',
            storage_local=True,
            video_location='/path/to/video',
            threshold=10,
            noise_level=5,
        )
        self.session.add(evt)
        self.session.commit()

        labeling = Labeling(
            decider='fake_model',
            decided_at=datetime.now(),
            labels=['label1', 'label2'],
            mask= [True, False, True],
            probabilities=[0.8, 0.2, 0.5],
            event=evt
        )
        self.session.add(labeling)
        self.session.commit()

        rtr_labeling = self.session.query(Labeling).filter_by(id=labeling.id).first()
        
        self.assertEqual(rtr_labeling.decider, 'fake_model')
        self.assertEqual(rtr_labeling.decided_at, labeling.decided_at)
        self.assertEqual(rtr_labeling.labels, ['label1', 'label2'])
        self.assertEqual(rtr_labeling.mask, [True, False, True])
        self.assertEqual(rtr_labeling.probabilities, [0.8, 0.2, 0.5])
        self.assertEqual(rtr_labeling.event, evt)
        self.assertEqual(rtr_labeling.event_id, evt.id)

    def test_true_label(self):
        evt = EventObservation(
            event_name='event1',
            video_file='video1.mp4',
            capture_time='2021-01-01T12:00:00',
            scene_name='scene1',
            storage_local=True,
            video_location='/path/to/video',
            threshold=10,
            noise_level=5,
        )
        self.session.add(evt)

        l1 = Labeling(
            decider='testuser',
            decided_at=datetime.now(),
            labels=['label3'],
            mask=None,
            probabilities=None,
            event=evt
        )
        self.session.add(l1)
        l2 = Labeling(
            decider='fake_model.pkl',
            decided_at=datetime.now(),
            labels=['label1'],
            mask=[True, False, False],
            probabilities=[.8, .2, .1],
            event=evt
        )
        self.session.add(l2)
        self.session.commit()

        rtr_evt = EventObservation.by_id(self.session, evt.id)
        self.assertEqual(rtr_evt.true_labeling, ['label3'])
        self.assertEqual(rtr_evt.true_labeling_as_string, 'label3')

    def test_classification_deprecation(self):
        evt = EventObservation(
            event_name='event1',
            video_file='video1.mp4',
            capture_time='2021-01-01T12:00:00',
            scene_name='scene1',
            storage_local=True,
            video_location='/path/to/video',
            threshold=10,
            noise_level=5,
        )
        self.session.add(evt)
        self.session.commit()

        l1 = Labeling(
            decider='testuser',
            decided_at=datetime.now(),
            labels=['label3', 'label4'],
            mask=None,
            probabilities=None,
        )
        evt.labelings.append(l1)

        l2 = Labeling(
            decider='fake_model.pkl',
            decided_at=datetime.now(),
            labels=['label1', 'label2', 'label3'],
            mask=[True, False, False],
            probabilities=[.8, .2, .1],
            event=evt
        )
        self.session.add(l2)
        c1 = EventClassification(
            classifier='testuser',
            classified_at=datetime.now(),
            label='class3',
            confidence=0.9,
            observation_id=evt.id
        )
        self.session.add(c1)
        self.session.commit()

        rtr_evt = EventObservation.by_name(self.session, 'event1')
        self.assertEqual(len(rtr_evt.labelings), 2)
        self.assertEqual(len(rtr_evt.classifications), 1)
        self.assertEqual(rtr_evt.all_labels, ['label1', 'label2', 'label3', 'label4'])

        self.assertEqual(rtr_evt.api_response_dict['labels'], ['label1', 'label2', 'label3', 'label4'])

    def test_nothingness(self):
        evt = EventObservation(
            event_name='event1',
            video_file='video1.mp4',
            scene_name='scene1',
        )
        self.session.add(evt)
        self.session.commit()
        
        rtr = EventObservation.by_name(self.session, 'event1')
        self.assertEqual(rtr.labelings, [])
        self.assertEqual(rtr.all_labels, None)
        self.assertEqual(rtr.api_response_dict['labels'], None)
        self.assertEqual(rtr.true_labeling, None)
        
        lbl1 = Labeling(
            decider='model1.pkl',
            labels=[],
            probabilities=[0.1, 0.2, 0.3],
            mask=[False, False, False],
        )
        evt.labelings.append(lbl1)
        self.session.commit()
        
        rtr = EventObservation.by_name(self.session, 'event1')
        self.assertEqual(rtr.labelings, [lbl1])
        self.assertEqual(rtr.all_labels, [])
        self.assertEqual(rtr.true_labeling, None)
        self.assertEqual(rtr.api_response_dict['labels'], [])

        lbl2 = Labeling(
            decider='testuser',
            decided_at=datetime.now(),
            labels=[],
        )
        evt.labelings.append(lbl2)
        self.session.commit()
        
        rtr = EventObservation.by_name(self.session, 'event1')
        self.assertEqual(rtr.labelings, [lbl1, lbl2])
        self.assertEqual(rtr.all_labels, [])
        self.assertEqual(rtr.true_labeling, [])
        

        


if __name__ == '__main__':
    unittest.main()