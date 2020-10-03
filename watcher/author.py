# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# @brief Author model

class Author(object):

	def __init__(self, watcher, author_id, trader_name):
		self._watcher = watcher
		self._id = author_id
		self._name = trader_name
		self._success_rate = 0
		self._last_trades = []
		self._risk_score = None

	@property
	def watcher(self):
		return self._watcher

	@property
	def id(self):
		return self._id

	@property
	def name(self):
		return self._name

	@property
	def last_trades(self):
		return self._last_trades

	@property
	def risk_score(self):
		return self._risk_score

	@risk_score.setter
	def risk_score(self, score):
		self._risk_score = score

	@property
	def success_rate(self):
		return self._success_rate

	@success_rate.setter
	def success_rate(self, success_rate):
		self._success_rate = success_rate
