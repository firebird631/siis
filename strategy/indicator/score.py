# @date 2018-09-21
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Indicator score computation helper

import numpy as np

from strategy.indicator import utils


class Score(object):

	__slots__ = '_current_score', '_last_score', '_sum_factor', '_scores', '_range', '_map'

	def __init__(self, min_scores=2, max_scores=16):
		self._current_score = 0.0
		self._last_score = 0.0
		self._sum_factor = 0.0
		self._scores = [0.0]*min_scores
		self._range = [min_scores, max_scores]
		self._map = {}

	def reset(self):
		self._scores = [0.0]*len(self._scores)
		self._last_score = 0.0
		self._sum_factor = 0.0
		self._current_score = 0.0
		self._map = {}

	def initialize(self):
		self._map = {}

	def finalize(self):
		"""Compute the last score and append to the history."""
		if self._sum_factor != 0.0:
			self._last_score = self._current_score / self._sum_factor
		else:
			self._last_score = 0.0

		self._scores.append(self._last_score)
		self._scores = self._scores[-self._range[1]:]
	
		self._sum_factor = 0.0
		self._current_score = 0.0	

	def add(self, score, factor, name=""):
		"""Add a score to the current score, it is scaled by factor and sum the factors."""
		self._current_score += score * factor
		self._sum_factor += factor

		if name:
			self._map[name] = (score, factor)

	def scale(self, scale):
		"""Apply a scalar to the current score."""
		self._current_score *= scale

	@property
	def last(self):
		return self._last_score

	@property
	def prev(self):
		return self._scores[-1]

	def trend(self):
		return utils.trend(self._scores)
	
	def trend_extremum(self):
		return utils.trend_extremum(self._scores)

	@property
	def data(self):
		return self._scores

	def distance(self):
		"""Distance of the two lasts scores."""
		if len(self._scores) < 2:
			return 0.0

		return self._scores[-1] - self._scores[-2]

	def is_cross_last(self, with_score):
		if len(self._scores) < 2:
			return False

		return utils.cross((self._scores[-2], with_score._scores[-2]), (self._scores[-1], with_score._scores[-1])) != 0

	def cross_at(self, with_score):
		# Cross along the whole array and return a list with -1 0 or 1 where cross down, no cross or cross up
		size = min(len(self._scores), len(with_score._scores))

		if size < 2:
			return []

		d1 = self._scores[-size:]
		d2 = with_score._scores[-size:]

		crosses = [0]*size

		for i in range(1, size):
			crosses[i] = utils.cross((d1[i-1], d2[i-1]), (d1[i], d2[i]))

		return crosses


class Scorify(object):
	"""
	Merge the last score, get the trend, use an increase factor,
	and use a temporal regression factor.
	"""

	__slots__ = '_trigger_level', '_increase_factor', '_regression_factor', '_buy_or_sell', '_score', '_last_score', \
				'_score_accum', '_scalar', '_sum_factor'

	def __init__(self, trigger_level, increase_factor=1.0, regression_factor=1.0):
		"""
		@param trigger_level
		@param increase_factor
		@param regression_factor
		"""
		self._trigger_level = trigger_level
		self._increase_factor = increase_factor
		self._regression_factor = regression_factor
		self._buy_or_sell = 0      # -1 sell 0 no signal 1 buy

		self._score = 0.0          # current computing score
		self._last_score = 0.0     # last computed score (consensus of the strategy)
		self._score_accum = 0.0    # score accumulator

		self._scalar = 1.0
		self._sum_factor = 0.0

	def add(self, score, factor):
		self._score += score * factor
		self._sum_factor += factor

	def scale(self, scalar):
		self._scalar *= scalar

	def finalize(self):
		# global score factor
		self._score *= self._scalar

		# handle a score convergence to avoid multiple signals
		if (self._last_score > 0 and self._score > 0) or (self._last_score < 0 and self._score < 0):
			# take part of the previous score to minimize its impact progressively
			self._score_accum = self._last_score * self._regression_factor

			# keep as final score
			self._score = self._score_accum  # yes or no... ?
			# self._last_score = self._score_accum  # probably not
		else:
			# score to accumulator
			self._score_accum += self._score * self._increase_factor

		if abs(self._score_accum) >= self._trigger_level:
			# signal
			self._buy_or_sell = np.sign(self._score)  # self._score_accum)

			# regression to avoid multiples successive signals
			self._score_accum *= self._regression_factor

			# store it as final score
			self._last_score = self._score
		else:
			self._buy_or_sell = 0

		# zero for the next pass
		self._score = 0.0
		self._sum_factor = 0.0
		self._scalar = 1.0

	@property
	def buy_or_sell(self):
		return self._buy_or_sell

	@property
	def last(self):
		return self._last_score

	@property
	def has_signal(self):
		return self._buy_or_sell != 0

	def zero_accum(self):
		self._score_accum = 0.0
		self._buy_or_sell = 0
