import os
import sys
import redis
import logging
from pathlib import Path

from rq import Queue

import configparser
import sqlalchemy
from sqlalchemy import create_engine

from sshtunnel import SSHTunnelForwarder


APPLICATION_CONFIG_FILE = 'application.cfg'

def in_docker() -> bool:
    return os.path.isfile('/.dockerenv') 


__all__ = ['TunneledConnection','application_config','redis_connection','in_docker', 'application_path_for']

def redis_connection():
    redis_host = os.environ.get('REDIS_HOST') or application_config('system','REDIS_HOST')
    return redis.Redis(host=redis_host)

_parser = None
def application_config(section_name: str='', config_variable: str='') -> str:
    global _parser
    
    envname = f"WATCHER_{section_name.upper()}_{config_variable.upper()}"

    configval = os.environ.get(envname)
    if configval:
        return configval

    file = os.environ.get('WATCHER_CONFIG', APPLICATION_CONFIG_FILE)

    if not file or not os.access(file, os.R_OK):
        raise FileNotFoundError(f"couldn't read config file {file}")

    # #configs = [c if c != None and os.path.isfile(c) for c in APPLICATION_CONFIGS]
    # configs = [c for c in APPLICATION_CONFIGS if c != None]

    if _parser == None:
        _parser = configparser.ConfigParser()
        _parser.read(file)

    if section_name:
        cfg = _parser[section_name]
        if config_variable:
            cfg_value = cfg.get(config_variable, None)
            #logging.debug(f"using {section_name}.{config_variable} = {cfg_value}")
            return cfg_value or ''
    else:
        cfg = _parser

    return cfg 

def application_path_for(file) -> Path:
    return Path(application_config('system','LOCAL_DATA_DIR')) / file

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

    def __exit__(self, *args):
        self.disconnect()

    def connect(self):
        if self.tunnel:
            self.tunnel.start()
            self.config['db_host'] = self.tunnel.local_bind_address[0]

        url, config_opts = get_db_url()
        self.engine = create_engine(url, **config_opts)
        self.connection = self.engine.connect()
        return self.connection

    def disconnect(self):
        self.connection.close()
        if self.tunnel and self.tunnel.is_active:
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

def get_db_url():
    db_config = get_db_config()
    
    if db_config.get('db_host'):
        if db_config.get("ssl_args"):
            return url_tcp_sslcerts_connection(db_config)
        else:
            return url_tcp_connection(db_config)
    elif db_config.get('db_user'):
        return url_unix_connection(db_config)
    else:
        return url_local_file_connection(db_config)

def url_local_file_connection(dbconfig):
    if not os.path.isfile(dbconfig['db_name']):
        raise FileNotFoundError(f"database file {dbconfig['db_name']} does not exist")

    return sqlalchemy.engine.url.URL.create(
        drivername=dbconfig['driver'],
        database=dbconfig['db_name']
    ), dbconfig['connection_config']

def url_tcp_sslcerts_connection(db_config):
    # Equivalent URL:
    # mysql+pymysql://<db_user>:<db_pass>@<db_host>:<db_port>/<db_name>
    return sqlalchemy.engine.url.URL.create(
        drivername=db_config['driver'],
        username=db_config['db_user'],
        password=db_config['db_pass'],
        host=db_config['db_host'],
        port=db_config['db_port'],
        database=db_config['db_name'],
        query={"ssl":True}
    ), db_config['connection_config']

def url_tcp_connection(db_config):
    # Equivalent URL:
    # mysql+pymysql://<db_user>:<db_pass>@<db_host>:<db_port>/<db_name>
    return sqlalchemy.engine.url.URL.create(
        drivername=db_config['driver'],
        username=db_config['db_user'],
        password=db_config['db_pass'],
        host=db_config['db_host'],
        port=db_config['db_port'],
        database=db_config['db_name']
    ), db_config['connection_config']

def url_unix_connection(db_config):
    # Equivalent URL:
    # mysql+pymysql://<db_user>:<db_pass>@/<db_name>?unix_socket=<socket_path>/<cloud_sql_instance_name>
    return sqlalchemy.engine.url.URL.create(
        drivername=db_config['driver'],
        username=db_config['db_user'],
        password=db_config['db_pass'],
        database=db_config['db_name'],
        query={
            "unix_socket": "{}/{}".format(
                db_config['db_socket_dir'],
                db_config['db_connection_name'])
        }
    ), db_config['connection_config']
