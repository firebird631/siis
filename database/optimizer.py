# @date 2019-01-04
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Candle market DB checker/optimizer.

import logging
logger = logging.getLogger('siis.database.optimizer')


class CandleOptimizer(object):
	"""
	Candle checker/optimizer for market.
	@todo
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
