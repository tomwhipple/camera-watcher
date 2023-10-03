import os
import sys
import redis
from rq import Queue

import configparser
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from sshtunnel import SSHTunnelForwarder

APPLICATION_CONFIG_FILE = 'application.cfg'

__all__ = ['TunneledConnection','application_config','redis_connection']

def redis_connection():
    redis_host = os.environ.get('REDIS_HOST') or application_config('system','REDIS_HOST')
    return redis.Redis(host=redis_host)

def application_config(section_name=None, config_variable=None):
    parser = configparser.ConfigParser()

    file = os.environ.get('WATCHER_CONFIG', os.path.join(sys.path[0],'application.cfg'))

    if not file or not os.access(file, os.R_OK):
        msg = f"couldn't read config file {file}"
        raise Exception(msg)

    parser.read(file)

    if section_name:
        cfg = parser[section_name]
        if config_variable:
            return cfg.get(config_variable, None)
    else:
        cfg = parser

    return cfg


def get_db_config():

    config = application_config('database')

    db_config = {
        'connection_config':{
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
        },

        'driver': get_config_val(config, 'DB_DRIVER', 'mysql+pymysql'),

        'db_file': get_config_val(config,'DB_FILE'),
        'db_host': get_config_val(config,'DB_HOST'),
        'db_user': get_config_val(config,'DB_USER'),
        'db_pass': get_config_val(config,'DB_PASS'),
        'db_name': get_config_val(config,'DB_NAME'),
        'db_port': int(get_config_val(config,'DB_PORT',3306)),

        'db_ssh_host': get_config_val(config,"DB_SSH_HOST"),
        'db_ssh_user': get_config_val(config,"DB_SSH_USER"),
        'db_ssh_private_key_file': get_config_val(config,"DB_SSH_PRIVATE_KEY_FILE", "~/.ssh/id_rsa"),

        'db_socket_dir': get_config_val(config, "DB_SOCKET_DIR", "/var/run/mysqld"),
        'db_connection_name': get_config_val(config,"INSTANCE_CONNECTION_NAME", "mysqld.sock"),
    }

    if get_config_val(config,'DB_CERT'):
        db_config['ssl_args'] = {
            "ssl_ca": get_conifg_val(config,"DB_ROOT_CERT"),
            "ssl_cert": get_conifg_val(config,"DB_CERT"),
            "ssl_key": get_conifg_val(config,"DB_KEY")
        }

    return db_config

class TunneledConnection(object):
    def __init__(self):
        self.config = get_db_config()

        self.tunnel = get_ssh_tunnel(self.config)
        self.engine = None
        self.connection = None

    def __enter__(self):
        return self.connect()

    def connect(self):
        if self.tunnel:
            self.tunnel.start()
            self.config['db_host'] = self.tunnel.local_bind_address[0]

        if self.config.get('db_host'):
            if self.config.get("ssl_args"):
                self.engine = init_tcp_sslcerts_connection_engine(self.config)
            else:
                self.engine = init_tcp_connection_engine(self.config)
        elif self.config.get('db_user'):
            self.engine = init_unix_connection_engine(self.config)
        else:
            self.engine = init_local_file_connection_engine(self.config)

        self.connection = self.engine.connect()
        return self.connection

    def __exit__(self, *args):
        self.connection.close()
        if self.tunnel and self.connection.closed:
            self.tunnel.close()

def get_config_val(cfg, key, default=None):
    return os.environ.get(key) or cfg.get(key) or default

def get_ssh_tunnel(db_config):
    if not db_config.get("db_ssh_host"):
        return

    tunnel = SSHTunnelForwarder(
            (db_config['db_ssh_host'],22),
            ssh_username=db_config['db_ssh_user'],
            ssh_pkey=db_config['db_ssh_private_key_file'],
            remote_bind_address=('127.0.0.1',db_config['db_port']),
            local_bind_address=('127.0.0.1',db_config['db_port']),
        )
    return tunnel

def init_local_file_connection_engine(db_config):
    pool = sqlalchemy.create_engine(
        sqlalchemy.engine.url.URL.create(
                drivername=db_config['driver'],
                database=db_config['db_name'],

        ),
        **db_config['connection_config']
    )
    return pool

def init_tcp_sslcerts_connection_engine(db_config):

    pool = sqlalchemy.create_engine(
        # Equivalent URL:
        # mysql+pymysql://<db_user>:<db_pass>@<db_host>:<db_port>/<db_name>
        sqlalchemy.engine.url.URL.create(
            drivername=db_config['driver'],
            username=db_config['db_user'],  # e.g. "my-database-user"
            password=db_config['db_pass'],  # e.g. "my-database-password"
            host=db_config['db_host'],  # e.g. "127.0.0.1"
            port=db_config['db_port'],  # e.g. 3306
            database=db_config['db_name']  # e.g. "my-database-name"
        ),
        connect_args={"ssl":ssl_args},
        **db_config['connection_config']
    )

    return pool


def init_tcp_connection_engine(db_config):

    pool = sqlalchemy.create_engine(
        # Equivalent URL:
        # mysql+pymysql://<db_user>:<db_pass>@<db_host>:<db_port>/<db_name>
        sqlalchemy.engine.url.URL.create(
            drivername=db_config['driver'],
            username=db_config['db_user'],  # e.g. "my-database-user"
            password=db_config['db_pass'],  # e.g. "my-database-password"
            host=db_config['db_host'],  # e.g. "127.0.0.1"
            port=db_config['db_port'],  # e.g. 3306
            database=db_config['db_name'],  # e.g. "my-database-name"
        ),
        **db_config['connection_config']
    )

    return pool


def init_unix_connection_engine(db_config):

    pool = sqlalchemy.create_engine(
        # Equivalent URL:
        # mysql+pymysql://<db_user>:<db_pass>@/<db_name>?unix_socket=<socket_path>/<cloud_sql_instance_name>
        sqlalchemy.engine.url.URL.create(
            drivername=db_config['driver'],
            username=db_config['db_user'],  # e.g. "my-database-user"
            password=db_config['db_pass'],  # e.g. "my-database-password"
            database=db_config['db_name'],  # e.g. "my-database-name"
            query={
                "unix_socket": "{}/{}".format(
                    db_config['db_socket_dir'],  # e.g. "/cloudsql
                    db_config['db_connection_name'])  # i.e "<PROJECT-NAME>:<INSTANCE-REGION>:<INSTANCE-NAME>"
            }
        ),
        **db_config['connection_config']
    )

    return pool
