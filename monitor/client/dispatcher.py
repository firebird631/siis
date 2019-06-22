# @date 2019-01-01
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Stream dispatcher

import time
import datetime
import copy
import sys
import traceback

from monitor.streamable import Streamable
from monitor.client.strategy.strategychart import StrategyChart
from monitor.client.strategy.strategyinfo import StrategyInfo

import logging
logger = logging.getLogger('client.dispatcher')


class Dispatcher(object):

	def __init__(self):
		self._global = {}
		self._strategies = {}
		self._charts = {}

	def on_message(self, msg):
		try:
			if msg['c'] == Streamable.STREAM_GENERAL:
				pass
			elif msg['c'] == Streamable.STREAM_TRADER:
				pass
			elif msg['c'] == Streamable.STREAM_STRATEGY:
				pass
			elif msg['c'] == Streamable.STREAM_STRATEGY_INFO:
				key = "%s:%s" % (msg['g'], msg['s'])
				strategy_info = self._strategies.get(key)

				if not strategy_info:
					strategy_info = StrategyInfo.create_info(msg)
					self._strategies[key] = strategy_info

				if strategy_info:
					strategy_info.on_info(msg)

				# subscribe here for debug only (have to do a command for that)
				# this case is for strategy signals data but we wan't to display them on charts
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
