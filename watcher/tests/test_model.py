import unittest

from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from watcher import Computation, EventObservation, EventClassification

class TestModels(unittest.TestCase):
    def setUp(self):
        # Create a test database in memory
        raw_sql = open('db/watcher.sql', 'r').read()
        statements = raw_sql.split(';')
    
        engine = create_engine('sqlite:///:memory:')
        Session = sessionmaker(bind=engine)
        self.session = Session()
        for s in statements:
            self.session.execute(text(s))
        self.session.commit()

    def test_computation(self):
        # Create a Computation instance
        comp = Computation(event_name="Test Event", method_name="Test Method")
        self.session.add(comp)
        self.session.commit()

        # Check that the Computation was added to the database
        comp_db = self.session.query(Computation).first()
        self.assertEqual(comp_db.event_name, "Test Event")
        self.assertEqual(comp_db.method_name, "Test Method")

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
        api_response = classification_db.api_response_dict()
        self.assertEqual(api_response['classification_id'], classification_db.id)
        self.assertEqual(api_response['event_observation_id'], event.id)
        self.assertEqual(api_response['label'], "Test Label")
        self.assertEqual(api_response['decider'], "Test Decider")
        self.assertEqual(api_response['confidence'], 0.8)
        self.assertEqual(api_response['decision_time'], classification_db.decision_time.isoformat())

if __name__ == '__main__':
    unittest.main()