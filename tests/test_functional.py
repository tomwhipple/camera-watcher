from datetime import datetime
import unittest
from base64 import b64encode
from watcher.connection import application_config
from watcher.tests.utils import create_db_from_sql
from api import db, create_app

from watcher import EventClassification, EventObservation

class TestFunctional(unittest.TestCase):
    def setUp(self):
        app = create_app(db_url='sqlite:///:memory:', testing=True)
        
        app.app_context().push()
        self.app_dbg = app
        self.app = app.test_client()

        _, self.apiuser = create_db_from_sql(db.engine)

        key = self.apiuser.reset_key()
        db.session.commit()

        credentials = b64encode(bytes(f"{self.apiuser.username}:{key}",'utf-8')).decode('utf-8')
        self.headers = {
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/json'
        }

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        return super().tearDown()

    def test_db_sanity(self):
        response = self.app.get('/dbtest')
        self.assertEqual(response.status_code, 200)
        self.assertIn('number_of_observations', response.json)
        self.assertEqual(response.json['number_of_observations'], 0)

        evt = EventObservation(
            video_file = 'test.mp4',
            event_name = 'test_event',
            scene_name = 'test_scene',
        )
        db.session.add(evt)
        db.session.commit()        

        response = self.app.get('/dbtest')
        self.assertEqual(response.status_code, 200)
        self.assertIn('number_of_observations', response.json)
        self.assertEqual(response.json['number_of_observations'], 1)

        response = self.app.get('/uncategorized', headers=self.headers)
        self.assertAlmostEqual(response.status_code, 200)
        self.assertEqual(len(response.json), 1)
        

    def test_manual_classify_of_prior_automated_classification(self):
        
        evt = EventObservation(
            video_file = 'test.mp4',
            event_name = 'test_event',
            scene_name = 'test_scene',
        )
        db.session.add(evt)

        class1 = EventClassification(
            event_id = evt.id,
            label = 'label_1',
            confidence = 0.8, # only auto-classified have a confidence
            decider = 'fake_model',
        )
        evt.classifications.append(class1)
        class2 = EventClassification(
            event_id = evt.id,
            label = 'label_2',
            confidence = 0.85,
            decider = 'fake_model',
        )
        evt.classifications.append(class2)
        db.session.commit()

        response = self.app.get('/uncategorized', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json), 1)

        event_data = response.json[0]
        event_data['labels'] = ['label_1', 'label_3']
        response = self.app.post('/classify', headers=self.headers, json=event_data)
        self.assertEqual(response.status_code, 201)
        
        self.assertListEqual(response.json, ['label_1', 'label_3'])

        response = self.app.get('/uncategorized', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json), 0)
        
    def test_redo_manual_classify(self):
        
        evt = EventObservation(
            video_file = 'test.mp4',
            event_name = 'test_event',
            scene_name = 'test_scene',
        )
        db.session.add(evt)

        class1 = EventClassification(
            event_id = evt.id,
            label = 'label_1',
            decider = self.apiuser.username,
        )
        evt.classifications.append(class1)
        class2 = EventClassification(
            event_id = evt.id,
            label = 'label_2',
            decider = self.apiuser.username,
        )
        evt.classifications.append(class2)
        db.session.commit()

        input_relabel = ['label_1', 'label_3']
        
        event_data = evt.api_response_dict
        event_data['labels'] = input_relabel
        response = self.app.post('/classify', headers=self.headers, json=event_data)
        self.assertEqual(response.status_code, 201)

        self.assertListEqual(response.json, input_relabel)

        evt_R = EventObservation.by_id(db.session, evt.id)

        self.assertEqual(evt_R.all_labels_as_string, ' & '.join(input_relabel))

    def test_app_classify_one(self):
        evt = EventObservation(
            video_file = 'test.mp4',
            video_location = 'some_dir',
            event_name = 'test_event',
            scene_name = 'test_scene',
        )
        db.session.add(evt)
        db.session.commit()
        
        response = self.app.get('/labels', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_json)
        self.assertEqual(response.json, [])
        
        expected_uncategorized = [
           {
               'video_file': 'test.mp4',
               'scene_name': 'test_scene',
               'event_observation_id': evt.id,
               'video_url': application_config('system','BASE_STATIC_PUBLIC_URL') + '/some_dir/test.mp4',
                'labels': None
               } 
        ]
        
        response = self.app.get('/uncategorized', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_json)
        self.assertEqual(len(response.json), 1)

        self.assertIsNotNone(response.json[0]['capture_time'])
        for k, v in expected_uncategorized[0].items(): 
            self.assertEqual(response.json[0][k], v)
        




if __name__ == '__main__':
    unittest.main()