import unittest
from api import db, create_app

from base64 import b64encode

from watcher.tests.utils import setup_test_db

class TestAPI(unittest.TestCase):
    def setUp(self):
        app = create_app(db_url='sqlite:///:memory:', testing=True)
        
        app.app_context().push()
        self.app = app.test_client()

        self.session, self.apiuser = setup_test_db(db.engine)

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

        data = {
            'labels': ['label1', 'label2'],
            'event_observation_id': 1
        }
        response = self.app.post('/classify', headers=self.headers, json=data)
        self.assertEqual(response.status_code, 201)
        self.assertIn('event_observation_id', response.json[0])

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

if __name__ == '__main__':
    unittest.main()