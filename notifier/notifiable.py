# @date 2018-08-08
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Notifable object

class Notifiable(object):

	def __init__(self, name):
		self._name = name

	def receiver(self, signal):
		pass

	@property
	def name(self):
		return self._name
