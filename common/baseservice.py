# @date 2018-08-08
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Base service object with receiver.

from abc import ABC, abstractmethod


class BaseService(ABC):
	"""
	Base service model. For synchronous or asynchronous services.
	@see Service
	"""

	def __init__(self, name: str):
		self._name = name

	@abstractmethod
	def receiver(self, signal):
		pass

	@property
	def name(self) -> str:
		return self._name
