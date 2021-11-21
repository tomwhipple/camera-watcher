#!/usr/bin/env python3

import sys
import json
import argparse
import pathlib
import os

from datetime import datetime

import sqlalchemy
from sqlalchemy.orm import Session

def init_connection_engine():
    db_config = {
        # [START cloud_sql_mysql_sqlalchemy_limit]
        # Pool size is the maximum number of permanent connections to keep.
        "pool_size": 5,
        # Temporarily exceeds the set pool_size if no connections are available.
        "max_overflow": 2,
        # The total number of concurrent connections for your application will be
        # a total of pool_size and max_overflow.
        # [END cloud_sql_mysql_sqlalchemy_limit]

        # [START cloud_sql_mysql_sqlalchemy_backoff]
        # SQLAlchemy automatically uses delays between failed connection attempts,
        # but provides no arguments for configuration.
        # [END cloud_sql_mysql_sqlalchemy_backoff]

        # [START cloud_sql_mysql_sqlalchemy_timeout]
        # 'pool_timeout' is the maximum number of seconds to wait when retrieving a
        # new connection from the pool. After the specified amount of time, an
        # exception will be thrown.
        "pool_timeout": 30,  # 30 seconds
        # [END cloud_sql_mysql_sqlalchemy_timeout]

        # [START cloud_sql_mysql_sqlalchemy_lifetime]
        # 'pool_recycle' is the maximum number of seconds a connection can persist.
        # Connections that live longer than the specified amount of time will be
        # reestablished
        "pool_recycle": 1800,  # 30 minutes
        # [END cloud_sql_mysql_sqlalchemy_lifetime]

    }

    if os.environ.get("DB_HOST"):
        if os.environ.get("DB_ROOT_CERT"):
            return init_tcp_sslcerts_connection_engine(db_config)
        return init_tcp_connection_engine(db_config)
    return init_unix_connection_engine(db_config)


def init_tcp_sslcerts_connection_engine(db_config):
    # [START cloud_sql_mysql_sqlalchemy_create_tcp_sslcerts]
    # Remember - storing secrets in plaintext is potentially unsafe. Consider using
    # something like https://cloud.google.com/secret-manager/docs/overview to help keep
    # secrets secret.
    db_user = os.environ["DB_USER"]
    db_pass = os.environ["DB_PASS"]
    db_name = os.environ["DB_NAME"]
    db_host = os.environ["DB_HOST"]
    db_root_cert = os.environ["DB_ROOT_CERT"]
    db_cert = os.environ["DB_CERT"]
    db_key = os.environ["DB_KEY"]

    # Extract port from db_host if present,
    # otherwise use DB_PORT environment variable.
    host_args = db_host.split(":")
    if len(host_args) == 1:
        db_hostname = host_args[0]
        db_port = int(os.environ.get("DB_PORT",3306))
    elif len(host_args) == 2:
        db_hostname, db_port = host_args[0], int(host_args[1])

    ssl_args = {
        "ssl_ca": db_root_cert,
        "ssl_cert": db_cert,
        "ssl_key": db_key
    }

    pool = sqlalchemy.create_engine(
        # Equivalent URL:
        # mysql+pymysql://<db_user>:<db_pass>@<db_host>:<db_port>/<db_name>
        sqlalchemy.engine.url.URL.create(
            #drivername="mysql+pymysql",
            drivername="mysql",
            username=db_user,  # e.g. "my-database-user"
            password=db_pass,  # e.g. "my-database-password"
            host=db_hostname,  # e.g. "127.0.0.1"
            port=db_port,  # e.g. 3306
            database=db_name  # e.g. "my-database-name"
        ),
        connect_args={"ssl":ssl_args},
        **db_config
    )
    # [END cloud_sql_mysql_sqlalchemy_create_tcp_sslcerts]

    return pool


def init_tcp_connection_engine(db_config):
    # [START cloud_sql_mysql_sqlalchemy_create_tcp]
    # Remember - storing secrets in plaintext is potentially unsafe. Consider using
    # something like https://cloud.google.com/secret-manager/docs/overview to help keep
    # secrets secret.
    db_user = os.environ["DB_USER"]
    db_pass = os.environ["DB_PASS"]
    db_name = os.environ["DB_NAME"]
    db_host = os.environ["DB_HOST"]

    # Extract port from db_host if present,
    # otherwise use DB_PORT environment variable.
    host_args = db_host.split(":")
    if len(host_args) == 1:
        db_hostname = db_host
        db_port = os.environ.get("DB_PORT",3306)
    elif len(host_args) == 2:
        db_hostname, db_port = host_args[0], int(host_args[1])

    pool = sqlalchemy.create_engine(
        # Equivalent URL:
        # mysql+pymysql://<db_user>:<db_pass>@<db_host>:<db_port>/<db_name>
        sqlalchemy.engine.url.URL.create(
            #drivername="mysql+pymysql",
            drivername="mysql",
            username=db_user,  # e.g. "my-database-user"
            password=db_pass,  # e.g. "my-database-password"
            host=db_hostname,  # e.g. "127.0.0.1"
            port=db_port,  # e.g. 3306
            database=db_name,  # e.g. "my-database-name"
        ),
        **db_config
    )
    # [END cloud_sql_mysql_sqlalchemy_create_tcp]

    return pool


def init_unix_connection_engine(db_config):
    # [START cloud_sql_mysql_sqlalchemy_create_socket]
    # Remember - storing secrets in plaintext is potentially unsafe. Consider using
    # something like https://cloud.google.com/secret-manager/docs/overview to help keep
    # secrets secret.
    db_user = os.environ["DB_USER"]
    db_pass = os.environ["DB_PASS"]
    db_name = os.environ["DB_NAME"]
    db_socket_dir = os.environ.get("DB_SOCKET_DIR", "/cloudsql")
    instance_connection_name = os.environ["INSTANCE_CONNECTION_NAME"]

    pool = sqlalchemy.create_engine(
        # Equivalent URL:
        # mysql+pymysql://<db_user>:<db_pass>@/<db_name>?unix_socket=<socket_path>/<cloud_sql_instance_name>
        sqlalchemy.engine.url.URL.create(
            #drivername="mysql+pymysql",
            drivername="mysql",
            username=db_user,  # e.g. "my-database-user"
            password=db_pass,  # e.g. "my-database-password"
            database=db_name,  # e.g. "my-database-name"
            query={
                "unix_socket": "{}/{}".format(
                    db_socket_dir,  # e.g. "/cloudsql"
                    instance_connection_name)  # i.e "<PROJECT-NAME>:<INSTANCE-REGION>:<INSTANCE-NAME>"
            }
        ),
        **db_config
    )
    # [END cloud_sql_mysql_sqlalchemy_create_socket]

    return pool


# This global variable is declared with a value of `None`, instead of calling
# `init_connection_engine()` immediately, to simplify testing. In general, it
# is safe to initialize your database connection pool when your script starts
# -- there is no need to wait for the first request.
db = None
db = init_connection_engine()

from watcher_model import EventObservation

def process_file(filename, conn):
	with open(filename) as fp:
		parsed_event = json.loads(fp.readline())
		conn.add(EventObservation(
				video_file=parsed_event['pathToVideo'],
				scene_name=parsed_event['instanceName'],
				capture_time=datetime.fromtimestamp(int(parsed_event['timestamp']))

			))

		conn.commit()

		print(parsed_event['pathToVideo'])



def main():
	parser = argparse.ArgumentParser(description='Upload events to database')
	parser.add_argument('-d', '--input_directory', type=pathlib.Path)
	#parser.add_argument('-f', '--files' type=argparse.FileType('r'))
	parser.add_argument('-l', '--limit', type=int)

	args = parser.parse_args()

	filelist = []

	if args.input_directory:
		for filename in os.listdir(args.input_directory):
			if filename.endswith(".jsonl"):
				filelist.append(os.path.join(args.input_directory,filename))
				if args.limit and len(filelist) >= args.limit:
					break



#	try:
	with db.connect() as conn:
		session = Session(db)
		for file in filelist:
			process_file(file, session)


#	except Exception as e:
#		print("Whooops!",file=sys.stderr)
#		print(e,file=sys.stderr)


if __name__ == "__main__":
	main()