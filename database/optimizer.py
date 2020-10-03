# @date 2019-01-04
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Candle market DB checker/optimizer.

import logging
logger = logging.getLogger('siis.database.optimizer')

from database.database import Database
from database.tickstorage import TickStorage, TickSteamer, TextToBinary


class OhlcOptimizer(object):
	"""
	Tick data optimizer/validate.
	
	@todo Check for missing Ohlc
	@todo Repair with missing Ohlc
	@todo Take care of week-end/off-market
	"""

	def __init__(self, db, broker_id, market_id):
		self._db = db

		self._broker_id = broker_id
		self._market_id = market_id

	def optimize(self):
		# @todo
		pass

	def detect_gaps(self):
		# @todo
		return []


class TickOptimizer(object):
	"""
	Tick data optimizer/validate.
	
	@todo Check for GAP of tick (Take care of week-end/off-market)
	@todo Reorder the ticks and recreate the file if necessary
	"""

	def __init__(self, broker_id, market_id):
		self._broker_id = broker_id
		self._market_id = market_id

	def optimize(self):
		# @todo
		pass

	def detect_gaps(self):
		# @todo
		return []
