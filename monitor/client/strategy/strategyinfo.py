# @date 2019-01-01
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Strategy info

from monitor.streamable import Streamable


class StrategyInfo(object):

	@staticmethod
	def create_info(data):
		if data['c'] == Streamable.STREAM_STRATEGY_INFO:
			info = StrategyInfo(data['g'], data['s'])
			return info

		return None

	def __init__(self, group_name: str, stream_name: str):
		self.chart = None

		self.strategy_identifier = group_name
		self.instrument_symbol = stream_name
		self.tfs = tuple()
		self.depth = tuple()

		self._visible = False

	def on_info(self, data: dict):
		if data['n'] == 'tfs':
			self.tfs = data['v']
		elif data['n'] == 'depth':
			self.depth = data['v']
		# @todo trades...
