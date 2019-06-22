# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# 1fox.com watcher implementation

import http.client
import urllib
import json
import datetime

from watcher.watcher import Watcher
from watcher.author import Author
from watcher.position import Position
from notifier.signal import Signal

from config import config

from terminal.terminal import Terminal


class OnFoxWatcher(Watcher):
	# @todo use the 1fox connector to watch social positions and live data (using ws)

	def __init__(self, service):
		super().__init__(service, name="1fox.com")

		self._host = "1fox.com"
		self._base_url = "/api/v1/"
