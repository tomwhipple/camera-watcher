import unittest
import pytest

from datetime import datetime
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from watcher import Computation, EventObservation, EventClassification, Labeling
from watcher.connection import application_config
from watcher.tests.utils import setup_test_db

class TestModels(unittest.TestCase):
    def setUp(self):
        self.session, _ = setup_test_db()

    def tearDown(self):
        self.session.close()
        
    def test_event_observation_has_name(self):
        event = EventObservation(video_file="test.mp4", 
                                 scene_name="Test Scene",
                                 event_name=None)
        err = None
        try:
            self.session.add(event)
            self.session.commit()
        except Exception as e:
            err = e
        finally:
            self.assertIsInstance(err, IntegrityError)

    def test_event_observation_name_is_unique(self):
        event1 = EventObservation(video_file="test1.mp4", 
                                 scene_name="Test Scene",
                                 event_name="test_event")
        event2 = EventObservation(video_file="test2.mp4", 
                                 scene_name="Test Scene",
                                 event_name="test_event")
        err = None
        try:
            self.session.add(event1)
            self.session.add(event2)
            self.session.commit()
        except Exception as e:
            err = e
        finally:
            self.assertIsInstance(err, IntegrityError)
        
    def test_event_observation(self):
        #event = EventObservation(video_file="test.mp4", scene_name="Test Scene")
        event = EventObservation(
            event_name='event1',
            video_file='video1.mp4',
            capture_time='2021-01-01T12:00:00',
            scene_name='scene1',
            storage_local=True,
            video_location='path/to/video',
            threshold=10,
            noise_level=5,
        )

        self.session.add(event)
        self.session.commit()

        # Check that the EventObservation was added to the database
        rtr_evt = EventObservation.by_name(self.session, 'event1')
        self.assertEqual(rtr_evt.event_name, 'event1')
        self.assertEqual(rtr_evt.video_file, "video1.mp4")
        self.assertEqual(rtr_evt.capture_time, datetime(2021, 1, 1, 12, 0, 0))
        self.assertEqual(rtr_evt.scene_name, 'scene1')
        self.assertFalse(rtr_evt.storage_local)
        self.assertEqual(rtr_evt.video_location, 'path/to/video')
        self.assertEqual(rtr_evt.threshold, 10)
        self.assertEqual(rtr_evt.noise_level, 5)
        
        self.assertEqual(rtr_evt.lighting_type, 'daylight')
        self.assertEqual(rtr_evt.file_path, 
                         Path(application_config('system', 'LOCAL_DATA_DIR')) / 'path/to/video' / 'video1.mp4')

        expected_url = application_config('system', 'BASE_STATIC_PUBLIC_URL') + '/path/to/video/video1.mp4'
        self.assertEqual(rtr_evt.video_url, expected_url)
                    
        self.assertIsNone(rtr_evt.significant_frame_file)
        self.assertEqual(rtr_evt.classifications,[])
        self.assertEqual(rtr_evt.labelings,[])
        self.assertEqual(rtr_evt.results,[])

        expected_api_response = {
            'event_observation_id': event.id,
            'video_file': 'video1.mp4',
            'capture_time': '2021-01-01T12:00:00-07:00',
            'scene_name': 'scene1',
            'video_url': expected_url,
            'labels': None
        }
        self.assertEqual(rtr_evt.api_response_dict, expected_api_response)
        

    def test_get_uncatetorized(self):
        # Create an EventObservation instance
        event = EventObservation(video_file="test.mp4", 
                                 scene_name="Test Scene", 
                                 event_name="test_event")
        self.session.add(event)
        self.session.commit()

        # Call the uncategorized method
        uncategorized = EventObservation.uncategorized(self.session, before=None, limit=10,
                                                       lighting=['daylight', 'night', 'twilight'])

        # Check that the returned list is correct
        self.assertEqual(len(uncategorized), 1)
        self.assertEqual(uncategorized[0].id, event.id)

        ## Check that old behavior isn't used
        classification = EventClassification(
            label="Test Label",
            decider="Test Decider",
            confidence=0.8,
            is_deprecated=False
        )
        event.classifications.append(classification)
        self.session.commit()

        uncategorized = EventObservation.uncategorized(self.session, before=None, limit=10,
                                                       lighting=['daylight', 'night', 'twilight'])

        self.assertEqual(len(uncategorized), 1)
        self.assertEqual(uncategorized[0].id, event.id)

        model_lbl = Labeling(
            decider='model.pkl',
            labels=['label4'],
            probabilities=[0.1, 0.2, 0.3, 0.9],
            mask=[False, False, False, True],
            event=event
        )
        event.labelings.append(model_lbl)
        self.session.commit()

        uncategorized = EventObservation.uncategorized(self.session, before=None, limit=10,
                                                       lighting=['daylight', 'night', 'twilight'])


        self.assertEqual(len(uncategorized), 1)
        self.assertEqual(uncategorized[0].id, event.id)

        true_lbl = Labeling(
            decider='testuser',
            decided_at=datetime.now(),
            labels=['label3'],
            event=event
        )
        self.session.add(true_lbl)
        self.session.commit()

        
        uncategorized = EventObservation.uncategorized(self.session, before=None, limit=10,
                                                         lighting=['daylight', 'night', 'twilight'])
        self.assertEqual(len(uncategorized), 0)
        

    def test_event_classification(self):
        # Create an EventObservation instance
        event = EventObservation(video_file="test.mp4", scene_name="Test Scene")
        self.session.add(event)
        self.session.commit()

        # Create an EventClassification instance
        classification = EventClassification(
            label="Test Label",
            decider="Test Decider",
            confidence=0.8,
            is_deprecated=False
        )
        event.classifications.append(classification)
        self.session.commit()

        # Check that the EventClassification was added to the database
        classification_db = self.session.query(EventClassification).first()
        self.assertEqual(classification_db.observation, event)
        self.assertEqual(classification_db.label, "Test Label")
        self.assertEqual(classification_db.decider, "Test Decider")
        self.assertAlmostEqual(classification_db.confidence, 0.8)
        self.assertFalse(classification_db.is_deprecated)
        self.assertIsInstance(classification_db.decision_time, datetime)

        # Check the API response dictionary
        api_response = classification_db.api_response_dict
        self.assertEqual(api_response['classification_id'], classification_db.id)
        self.assertEqual(api_response['event_observation_id'], event.id)
        self.assertEqual(api_response['label'], "Test Label")
        self.assertEqual(api_response['decider'], "Test Decider")
        self.assertEqual(api_response['confidence'], 0.8)
        self.assertEqual(api_response['decision_time'], classification_db.decision_time.isoformat())

    def test_unique_labels(self):
        # Create an EventClassification instance
        event = EventObservation(video_file="test.mp3", scene_name="Test Scene")
        self.session.add(event)
        self.session.commit()

        # Create multiple EventClassification instances with unique labels
        classification0 = EventClassification(
            label="class 0",
            decider="Decider 0",
            confidence=None,
            is_deprecated=None
        )
        event.classifications.append(classification0)

        lbl1 = Labeling(
            decider='testuser',
            decided_at=datetime.now(),
            labels=['A', 'B', 'C'],
        )
        event.labelings.append(lbl1)
        
        lbl2 = Labeling(
            decider='testuser',
            decided_at=datetime.now(),
            labels=['A', 'D'],
            mask=[True, False, False, True],
            probabilities=[0.8, 0.2, 0.1, 0.9],
        )
        event.labelings.append(lbl2)

        self.session.commit()

        classifications = EventClassification.UniqueLabels(self.session)
        self.assertEqual(classifications, ['class 0'])

        labels = Labeling.UniqueLabels(self.session)
        expected_labels = ['A', 'B', 'C', 'D']
        self.assertEqual(labels, expected_labels)

    def test_computation(self):
        # Create an EventObservation instance
        event_name_val = "test_event"
        event = EventObservation(video_file="test.mp4", scene_name="Test Scene", event_name=event_name_val)
        self.session.add(event)
        self.session.commit()

        # Create a Computation instance
        comp = Computation(event_name=event_name_val, 
                           method_name="Test Method", 
                           result_file="test_result_f12.jpg",
                           result_file_location="test_result_location",
                           success=True)
        self.session.add(comp)
        comp2 = Computation(event_name=event_name_val, method_name="Test Method", success=False)
        self.session.add(comp2)
        self.session.commit()

        evt = EventObservation.by_name(self.session, event_name_val)

        # Check that the Computation is correctly associated with the EventObservation
        self.assertEqual(len(evt.computations), 2)
        self.assertEqual(event.computations[0], comp)
        
        self.assertIsInstance(comp.result_file_fullpath, Path)
        self.assertTrue(str(comp.result_file_fullpath).startswith(application_config('system', 'LOCAL_DATA_DIR')))



if __name__ == '__main__':
    unittest.main()