
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from watcher.remote import APIUser

def create_db_from_sql(engine=None) -> Session:
    if not engine:
        engine = create_engine('sqlite:///:memory:')
    session = sessionmaker(bind=engine)()

    raw_sql = open('db/watcher.sql', 'r').read()
    statements = raw_sql.split(';')
    for s in statements:
        session.execute(text(s))

    testuser = APIUser(username="testuser")
    session.add(testuser)
    session.commit()

    return session, testuser

def create_db_from_object_model(base, engine=None) -> Session:
    try:
        os.unlink('test.sqlite3')
    except FileNotFoundError:
        pass
    
    if not engine:
        engine = create_engine('sqlite:///test.sqlite3', echo=False)
    session = sessionmaker(bind=engine)()
    
    base.metadata.create_all(engine)

    return session