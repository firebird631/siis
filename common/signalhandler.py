# @date 2018-08-08
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Signal handler

import logging
error_logger = logging.getLogger('siis.signalhandler')


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
			try:
				listener.receiver(signal)
			except Exception as e:
				error_logger.error(str(e))
