# @date 2019-01-03
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# www.alphavantage.co data fetcher

import json
import time
import traceback

from watcher.fetcher import Fetcher

from connector.alphavantage.connector import Connector
from terminal.terminal import Terminal

import logging
logger = logging.getLogger('siis.fetcher.alphavantage')
error_logger = logging.getLogger('siis.error.fetcher.alphavantage')


class AlphaVantageFetcher(Fetcher):
	"""
	AlphaVantage market data fetcher.
	"""

	def __init__(self, service):
		super().__init__("alphavantage.co", service)

		self._connector = None

	def connect(self):
		super().connect()

		try:
			identity = self.service.identity(self._name)
			self._subscriptions = []  # reset previous list

			if identity:
				self._connector = Connector(self.service, identity.get('api-key'),  identity.get('host'))
				self._connector.connect()

				# # @todo fetch crypto, currency, stocks
				# markets = self.fetch_markets()

				# self._markets_map['MSFT'] = (AlphaVantageWatcher.MARKET_STOCK, 'MSFT', None, 0.0)

				# all_stocks = []
				# all_stocks.append('MSFT')

				# if '*' in self.configured_symbols():
				# 	self._available_instruments = set(all_stocks)
				# 	instruments = all_instruments
				# else:
				# 	instruments = self.configured_symbols()

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
		# there is no authentication process, only an API key for each GET call.
		return self._connector

	def has_instrument(self, instrument, fetch_option=""):
		# we only have a list of currency so assume it can exists...
		return True

	def fetch_trades(self, market_id, from_date=None, to_date=None, n_last=None, fetch_option=""):
		pass

	def fetch_candles(self, market_id, timeframe, from_date=None, to_date=None, n_last=None, fetch_option=""):
		candles = []
		if not fetch_option or fetch_option == 'STOCK':
			market_type = Connector.MARKET_STOCK
			symbol = market_id

			try:
				candles = self._connector.fetch_stock(symbol, timeframe)
			except Exception as e:
				logger.error("Fetcher %s cannot retrieve candles %s on market %s" % (self.name, timeframe, symbol))
				logger.error(repr(e))

		elif fetch_option == 'CRYPTO' or fetch_option == 'FX':
			if fetch_option == 'CRYPTO':
				market_type = Connector.MARKET_CRYPTO
			elif fetch_option == 'FX':
				market_type = Connector.MARKET_FOREX
			else:
				return

			parts = market_id.split('.')

			symbol = parts[0]
			currency = parts[1]

			try:
				if parts[0] == 'CRYPTO':
					candles = self._connector.fetch_crypto(symbol, currency, timeframe)
				elif parts[0] == 'FX':
					candles = self._connector.fetch_forex(symbol, currency, timeframe)
			except Exception as e:
				logger.error("Fetcher %s cannot retrieve candles %s on market %s" % (self.name, timeframe, symbol+currency))
				logger.error(repr(e))				

		count = 0
		
		for candle in candles:
			count += 1
			# (timestamp, open, high, low, close, spread, volume)
			yield([candle[0], candle[1], candle[2], candle[3], candle[4], 0.0, candle[5]])

		logger.info("Fetcher %s has retrieved on market %s %s candles for timeframe %s" % (self.name, market_id, count, timeframe))
