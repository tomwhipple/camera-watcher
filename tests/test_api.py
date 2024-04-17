import unittest
from api import db, create_app

from base64 import b64encode

from watcher import EventObservation
from watcher.model import IntermediateResult
from watcher.tests.utils import create_db_from_sql

class TestAPI(unittest.TestCase):
    def setUp(self):
        app = create_app(db_url='sqlite:///:memory:', testing=True)
        
        app.app_context().push()
        self.app = app.test_client()

        self.session, self.apiuser = create_db_from_sql(db.engine)

        key = self.apiuser.reset_key()
        self.session.commit()

        credentials = b64encode(bytes(f"{self.apiuser.username}:{key}",'utf-8')).decode('utf-8')
        self.headers = {
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/json'
        }

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        return super().tearDown()

    def test_hello(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.decode(), "Hello. We're watching you.\n")

    def test_test_database(self):
        response = self.app.get('/dbtest')
        self.assertEqual(response.status_code, 200)
        self.assertIn('number_of_observations', response.json)
        self.assertEqual(response.json['number_of_observations'], 0)

    def test_get_uncategorized(self):
        response = self.app.get('/uncategorized', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json, list)

    def test_get_labels(self):
        response = self.app.get('/labels', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json, list)

    def test_auth(self):
        headers = self.headers.copy()
        headers.pop('Authorization')
        response = self.app.get('/labels', headers=headers)
        self.assertEqual(response.status_code, 401)

    def test_classify(self):
        data = {
            'filetype': 8,
            'event_name': 'test_event',
            'video_file': 'test_video.mp4',
            'scene_name': 'test_scene'
        }
        response = self.app.post('/observations', headers=self.headers, json=data)
        self.assertIn(response.status_code, [200, 201])
        
        event_observation_id = response.json['event_observation_id']
        self.assertGreater(event_observation_id, 0)
        
        data = {
            'labels': ['label1', 'label2', 'label3'],
            'event_observation_id': event_observation_id
        }
        response = self.app.post('/classify', headers=self.headers, json=data)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.is_json)

        self.assertEqual(response.json, data['labels'])

        evt = EventObservation.by_id(self.session,event_observation_id)
        self.assertEqual(evt.all_labels_as_string, ' & '.join(data['labels']))

    def test_create_event_observation(self):
        data = {
            'filetype': 8,
            'event_name': 'test_event',
            'video_file': 'test_video.mp4',
            'scene_name': 'test_scene'
        }
        response = self.app.post('/observations', headers=self.headers, json=data)
        self.assertIn(response.status_code, [200, 201])
        self.assertIn('event_observation_id', response.json)

    def test_significant_frame(self):
        data = {
            'filetype': 8,
            'event_name': 'test_event',
            'video_file': 'test_video.mp4',
            'scene_name': 'test_scene'
        }
        response = self.app.post('/observations', headers=self.headers, json=data)
        self.assertIn(response.status_code, [200, 201])

        evt_id=response.json['event_observation_id']
        self.assertIsInstance(evt_id, int)

        ir = IntermediateResult(
            step='task_save_significant_frame',
            event_id=evt_id,
            info={"duration": 13.826367, "most_significant_frame": 77, "number_of_frames": 215},
            file='test.jpg'
        )
        db.session.add(ir)
        db.session.commit()

        response = self.app.get('/uncategorized', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        respitem = response.json[0]
        self.assertIsInstance(respitem, dict)

        self.assertDictContainsSubset({
            'significant_frame_number':77,
            'significant_frame_image':'test.jpg'
        },respitem)

if __name__ == '__main__':
    unittest.main()