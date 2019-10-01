# @date 2019-01-04
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# HTTPS connector for degiro.nl

import requests

from terminal.terminal import Terminal

import logging
logger = logging.getLogger('siis.connector.degiro')


class Connector(object):
	"""
	API is not really official so its a workaround. But notice that your account could be warned or locked.
	@todo
	"""

	def __init__(self, service, api_key, api_secret, symbols, host="degiro.nl", callback=None):
		self._protocol = "https://"
		self._host = host or "degiro.nl"

		self._base_url = "/api/"
		self._timeout = 7   
		self._retries = 0  # initialize counter
		
		# REST API
		self._session = None
