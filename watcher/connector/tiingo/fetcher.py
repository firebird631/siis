# @date 2019-01-04
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# www.tiingo.com data fetcher

import json
import time
import traceback

from watcher.fetcher import Fetcher

from connector.tiingo.connector import Connector
from terminal.terminal import Terminal

import logging
logger = logging.getLogger('siis.fetcher.tiingo')
logger = logging.getLogger('siis.error.fetcher.tiingo')


class TiingoFetcher(Fetcher):
	"""
	Tiingo market data fetcher.
	"""

	def __init__(self, service):
		super().__init__("tiingo.com", service)

		self._connector = None

	def connect(self):
		super().connect()

		try:
			identity = self.service.identity(self._name)
			self._subscriptions = []  # reset previous list

			if identity:
				self._connector = Connector(self.service,  identity.get('api-key'),  identity.get('host'))
				self._connector.connect()

		except Exception as e:
			logger.error(repr(e))
			logger.error(traceback.format_exc())

			self._connector = None

	@property
	def connector(self):
		return self._connector

	@property
	def connected(self):
		return self._connector is not None and self._connector.connected

	def disconnect(self):
		super().disconnect()

		try:
			if self._connector:
				self._connector.disconnect()
				self._connector = None

		except Exception:
			error_logger.error(traceback.format_exc())

	@property
	def authenticated(self):
		return self._connector  # and self._connector.authenticated

	def has_instrument(self, instrument, fetch_option=""):
		# @todo could make a call to check if the market exists
		return True

	def fetch_trades(self, market_id, from_date=None, to_date=None, n_last=None, fetch_option=""):
		pass

	def fetch_candles(self, market_id, tf, from_date=None, to_date=None, n_last=None, fetch_option=""):
		candles = []

		try:
			candles = self._connector.fetch_symbol(market_id, tf)
		except Exception as e:
			logger.error("Fetcher %s cannot retrieve candles %s on market %s" % (self.name, tf, symbol))
			logger.error(repr(e))

		count = 0

		for candle in candles:
			count += 1
			# (timestamp, open bid, high, low, open, close, open ofr, high, low, close, volume)
			yield([candle[0], candle[2], candle[3], candle[1], candle[4], candle[2], candle[3], candle[1], candle[4], candle[5]])

		logger.info("Fetcher %s has retrieved on market %s %s candles for timeframe %s" % (self.name, market_id, count, tf))
