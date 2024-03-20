import unittest

from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from watcher import Computation, EventObservation, EventClassification
from watcher.connection import application_config
from watcher.tests.utils import setup_test_db

class TestModels(unittest.TestCase):
    def setUp(self):
        self.session, _ = setup_test_db()
        
    def test_event_observation(self):
        # Create an EventObservation instance
        event = EventObservation(video_file="test.mp4", scene_name="Test Scene")
        self.session.add(event)
        self.session.commit()

        # Check that the EventObservation was added to the database
        event_db = self.session.query(EventObservation).first()
        self.assertEqual(event_db.video_file, "test.mp4")
        self.assertEqual(event_db.scene_name, "Test Scene")

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
            label="Label 0",
            decider="Decider 0",
            confidence=None,
            is_deprecated=None
        )
        classification1 = EventClassification(
            label="Label 1",
            decider="Decider 1",
            confidence=None,
            is_deprecated=None
        )
        classification2 = EventClassification(
            label="Label 2",
            decider="Decider 2",
            confidence=None,
            is_deprecated=None
        )
        event.classifications.extend([classification0, classification1, classification2])
        self.session.commit()

        # Call the UniqueLabels method
        labels = EventClassification.UniqueLabels(self.session)

        # Check that the returned labels are correct
        expected_labels = ["Label 0", "Label 1", "Label 2"]
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