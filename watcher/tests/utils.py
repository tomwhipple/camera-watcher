
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from watcher.remote import APIUser

def setup_test_db(engine=None) -> Session:
    raw_sql = open('db/watcher.sql', 'r').read()
    statements = raw_sql.split(';')

    if not engine:
        engine = create_engine('sqlite:///:memory:')
    Session = sessionmaker(bind=engine)
    session = Session()
    for s in statements:
        session.execute(text(s))

    testuser = APIUser(username="testuser")
    session.add(testuser)
    session.commit()

    return session, testuser
