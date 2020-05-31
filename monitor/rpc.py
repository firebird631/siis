# @date 2019-07-03
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# RPC commands

import time


class Rpc(object):

    TARGET_UNDEFINED = 0
    TARGET_SYSTEM = 1
    TARGET_WATCHER = 2
    TARGET_TRADER = 3
    TARGET_STRATEGY = 4

    STREAM_STRATEGY_CHART = 3
    STREAM_STRATEGY_INFO = 4
    STREAM_STRATEGY_TRADE = 5

    STRATEGY_TRADE_ENTRY = 100
    STRATEGY_TRADE_MODIFY = 101
    STRATEGY_TRADE_EXIT = 102
    STRATEGY_TRADE_INFO = 103
    STRATEGY_TRADE_ASSIGN = 104
    STRATEGY_TRADE_CLEAN = 105
    STRATEGY_TRADE_EXIT_ALL = 109

    STRATEGY_TRADER_MODIFY = 200
    STRATEGY_TRADER_INFO = 201

    def __init__(self):
        self.target = TARGET_UNDEFINED
        self.command = -1
        self.timestamp = 0
        self.data = {}

    def define(self, target, command, data, timestamp=None):
        self.target = target
        self.command = command
        self.timestamp = timestamp or time.time()
        self.data = data

    def dumps(self):
        return {'t': self.target, 'c': self.command, 'd': self.data, 'T': time.time()}

    def loads(self, message):
        self.target = message.get('t', Rpc.TARGET_UNDEFINED)
        self.command = message.get('c', -1)
        self.timestamp = message.get('T', 0)
        self.data = message.get('d', {})
