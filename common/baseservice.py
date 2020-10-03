# @date 2018-08-08
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Base service object with receiver.

class BaseService(object):

	def __init__(self, name):
		self._name = name

	def receiver(self, signal):
		pass

	@property
	def name(self):
		return self._name
