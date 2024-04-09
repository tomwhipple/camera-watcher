import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from watcher.remote import APIUser
from watcher.tests.utils import create_db_from_sql

class TestAPIUser(unittest.TestCase):
    def setUp(self):
        # Create a test database in memory
        self.session, _ = create_db_from_sql()
        
    def test_newuser(self):
        newuser = APIUser(username="newuser")
        self.session.add(newuser)
        self.session.commit()
        
        not_user = APIUser.lookup_verify(self.session, "newuser", 'INVALID')
        self.assertIsNone(not_user)
        
        user = APIUser.lookup(self.session, "newuser")
        self.assertIsInstance(user, APIUser)
        self.assertEqual(user.username, "newuser")

    def test_reset_key(self):
        user = APIUser.lookup(self.session, "testuser")
        newkey = user.reset_key()
        self.session.commit()
        
        self.assertIsNotNone(newkey)
        self.assertEqual(len(newkey), 16)
        self.assertNotEqual(newkey, user.key_hash)

        self.assertTrue(user.verify_key(newkey))

    def test_lookup_fails(self):
        notuser = APIUser.lookup(self.session, "notuser")
        self.assertIsNone(notuser)
        
    def test_lookup_verify_fails(self):
        not_user = APIUser.lookup_verify(self.session, "testuser", 'INVALID')
        self.assertIsNone(not_user)
    
        not_user = APIUser.lookup_verify(self.session, "testuser", '')
        self.assertIsNone(not_user)
    
        not_user = APIUser.lookup_verify(self.session, "testuser", None)
        self.assertIsNone(not_user)
    
        user = APIUser.lookup(self.session, "testuser")
        self.assertIsInstance(user, APIUser)
        self.assertFalse(user.verify_key(user.key_hash))
        
        key = user.reset_key()
        not_user = APIUser.lookup_verify(self.session, "", key)
        self.assertIsNone(not_user)
        
if __name__ == '__main__':
    unittest.main()