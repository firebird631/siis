# @date 2023-05-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# REDIS client

import json
import time
from importlib import import_module

import logging

from monitor.streamable import Streamable

logger = logging.getLogger('siis.monitor.redisclient')
error_logger = logging.getLogger('siis.error.monitor.redisclient')
traceback_logger = logging.getLogger('siis.traceback.monitor.redisclient')


class RedisClient(object):

    def __init__(self, host: str, port: int, password: str, monitor_service,
                 strategy_service, trader_service, watcher_service, view_service):

        self._db = None
        self._conn_str = ""
        self.redis = import_module('redis', package='')

        self._host = host
        self._port = port
        self._password = password

        self._monitor_service = monitor_service
        self._strategy_service = strategy_service
        self._trader_service = trader_service
        self._watcher_service = watcher_service
        self._view_service = view_service

        self._stream_groups = set()

    def start(self):
        try:
            self._db = self.redis.Redis(host=self._host, port=self._port, password=self._password)

            # over SSL
            # self._db = redis.Redis.from_url(url='rediss://:password@hostname:port/0',
            #                          password='password',
            #                          ssl_keyfile='path_to_keyfile',
            #                          ssl_certfile='path_to_certfile',
            #                          ssl_cert_reqs='required',
            #                          ssl_ca_certs='path_to_ca_cert')

        except Exception as e:
            error_logger.error(str(e))

    def stop(self):
        if self._db:
            self.cleanup()
            self._db = None

    def cleanup(self):
        for stream_group in self._stream_groups:
            prefix = stream_group + ":*"

            for key in self._db.scan_iter(prefix):
                self._db.delete(key)

    @staticmethod
    def gen_strategy_trade_key(stream_category, stream_group, stream_name, content) -> str:
        return "%s:%i:%s:%i" % (stream_group, stream_category, stream_name, content['v']['id'])

    @staticmethod
    def gen_strategy_trader_key(stream_category, stream_group, stream_name, content) -> str:
        return "%s:%i:%s" % (stream_group, stream_category, stream_name)

    @staticmethod
    def gen_strategy_chart_key(stream_category, stream_group, stream_name, content) -> str:
        return "%s:%i:%s" % (stream_group, stream_category, stream_name)

    @staticmethod
    def gen_status_key(stream_category, stream_group, stream_name, content) -> str:
        return "%s:%i:%s" % (stream_group, stream_category, stream_name)

    def publish(self, stream_category, stream_group, stream_name, content):
        if not content:
            return

        key = ""

        if stream_category == Streamable.STREAM_STRATEGY_TRADE:
            if content.get('n') == 'trade-update':
                if not self._monitor_service.redis_stream_strategy_trade_update:
                    # ignored
                    return
            else:
                if not self._monitor_service.redis_stream_strategy_trade_ex:
                    # ignored
                    return

            key = self.gen_strategy_trade_key(stream_category, stream_group, stream_name, content)

        elif stream_category == Streamable.STREAM_TRADER:
            if not self._monitor_service.redis_stream_strategy_trader:
                # ignored
                return

            key = self.gen_strategy_trader_key(stream_category, stream_group, stream_name, content)

        elif stream_category == Streamable.STREAM_STRATEGY_INFO:
            if not self._monitor_service.redis_stream_status:
                # ignored
                return

            key = self.gen_status_key(stream_category, stream_group, stream_name, content)

        elif stream_category == Streamable.STREAM_STRATEGY_CHART:
            if not self._monitor_service.redis_stream_strategy_chart:
                # ignored
                return

            key = self.gen_strategy_chart_key(stream_category, stream_group, stream_name, content)

        if not key:
            return

        if stream_group not in self._stream_groups:
            self._stream_groups.add(stream_group)

        self._db.set(key, json.dumps(content))
