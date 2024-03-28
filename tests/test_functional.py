import unittest
from base64 import b64encode
from watcher.tests.utils import setup_test_db
from api import db, create_app

from watcher import EventClassification, EventObservation

class TestFunctional(unittest.TestCase):
    def setUp(self):
        app = create_app(db_url='sqlite:///:memory:', testing=True)
        
        app.app_context().push()
        self.app_dbg = app
        self.app = app.test_client()

        _, self.apiuser = setup_test_db(db.engine)

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

        # import pdb; pdb.set_trace()
        
        self.assertEqual(evt_R.all_labels_as_string, ' & '.join(input_relabel))
