# @date 2019-01-01
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Stream dispatcher

import traceback

from monitor.streamable import Streamable
from monitor.client.strategy.strategychart import StrategyChart
from monitor.client.strategy.strategyinfo import StrategyInfo

import logging
logger = logging.getLogger('siis.client.dispatcher')


class Dispatcher(object):

    def __init__(self):
        self._strategies = {}
        self._charts = {}

    def on_message(self, msg):
        try:
            if msg['c'] == Streamable.STREAM_STRATEGY_INFO:
                key = "%s:%s" % (msg['g'], msg['s'])
                strategy_info = self._strategies.get(key)

                if not strategy_info:
                    strategy_info = StrategyInfo.create_info(msg)
                    self._strategies[key] = strategy_info

                if strategy_info:
                    strategy_info.on_info(msg)

                # this case is for strategy signals data but we want to display them on charts
                for k, chart in self._charts.items():
                    if k.startswith(key+':'):
                        # propagate on each chart of this instrument
                        chart.on_chart(msg)

            elif msg['c'] == Streamable.STREAM_STRATEGY_CHART:
                key = "%s:%s" % (msg['g'], msg['s'])

                # subscribe here for debug only (have to do a command for that)
                chart = self._charts.get(key)
                if not chart:
                    chart = StrategyChart.create_chart(msg)
                    self._charts[key] = chart

                if chart:
                    chart.on_chart(msg)

        except Exception as e:
            logger.error(repr(e))
            logger.error(traceback.format_exc())

    def close(self):
        messages = []

        for key, chart in self._charts.items():
            a, m, tf = key.split(':')
            messages.append({'g': a, 's': m, 'c': Streamable.STREAM_STRATEGY_CHART, 'n': 'close', 't': 'cl', 'v': int(tf)})

        for key, strategy in self._strategies.items():
            a, m = key.split(':')
            messages.append({'g': a, 's': m, 'c': Streamable.STREAM_STRATEGY_INFO, 'n': 'close', 't': 'cl', 'v': None})

        return messages
