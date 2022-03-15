# @date 2018-09-15
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Key mapped object.

from __future__ import annotations

from typing import Union


class Keyed(object):
	"""
	Keyed object.
	"""

	__slots__ = '_key'

	_key: Union[str, None]

	def __init__(self):
		self._key = None

	@property
	def key(self) -> str:
		return self._key

	def set_key(self, key: str):
		self._key = key
