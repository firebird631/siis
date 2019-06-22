# @date 2018-09-15
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Key mapped object.


class Keyed(object):
	"""
	Keyed object.
	"""

	def __init__(self):
		self._key = None

	@property
	def key(self):
		return self._key

	def set_key(self, key):
		self._key = key
