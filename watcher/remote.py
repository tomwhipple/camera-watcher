import string
import random

from sqlalchemy import Column, Integer, String, DateTime, BigInteger
from sqlalchemy.orm import declarative_base

from datetime import datetime, timezone
from passlib.hash import pbkdf2_sha256

Base = declarative_base()

__all__ = ['APIUser', 'Upload']

class APIUser(Base):
    __tablename__ = 'api_users'
    id = Column(BigInteger, primary_key=True)
    username = Column(String(128),index = True)
    key_hash = Column(String(256))

    def reset_key(self):
        newkey = ''.join(random.choice(string.ascii_letters + string.digits) for i in range(16))
        self.key_hash = pbkdf2_sha256.hash(newkey)

        return newkey

    def verify_key(self, input_str):
        return pbkdf2_sha256.verify(input_str, self.key_hash)

class Upload(Base):
    __tablename__ = 'uploads'
    id = Column(BigInteger, primary_key=True)
    sync_at = Column(DateTime)
    object_class = Column(String)
    object_id = Column(BigInteger)
    http_status = Column(Integer)
    upload_batch = Column(String)

    def __init__(self, **input):
        self.__dict__.update(input)
        self.sync_at = datetime.now(timezone.utc)

        event = input.get('event') or input.get('object')
        if event:
            self.object_id = event.id
            self.object_class = type(event).__name__

