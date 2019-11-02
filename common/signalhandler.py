# @date 2018-08-08
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Signal handler

class SignalHandler(object):

	def __init__(self, service):
		self._service = service
		self._listeners = []

	def add_listener(self, listener):
		self._listeners.append(listener)

	def remove_listener(self, listener):
		self._listeners.remove(listener)

	def notify(self, signal):
		for listener in self._listeners:
			listener.receiver(signal)
