# @date 2019-01-04
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# alphavantage.co connector implementation

import time
import json
import base64
import requests

from datetime import datetime
from instrument.instrument import Instrument
from common.utils import UTC

from terminal.terminal import Terminal

import logging
logger = logging.getLogger('siis.connector.alphavantage')


class Connector(object):
	"""
	AlphaVantage HTTP GET connector.

	>> https://www.alphavantage.co/documentation/

	- crypto list : https://www.alphavantage.co/digital_currency_list/
	- currency list: https://www.alphavantage.co/physical_currency_list/

	@note API call frequency is 5 calls per minute and 500 calls per day.
	@todo Support max call frequency
	"""

	INTRADAY_TF_MAP = {
		60: '1min',
		5*60: '5min',
		15*60: '15min',
		30*60: '30min',
		60*60: '60min'
	}

	MARKET_STOCK = 0
	MARKET_FOREX = 1
	MARKET_CRYPTO = 2

	def __init__(self, service, api_key, host="www.alphavantage.co", protocol="https://"):
		self._host = host or "www.alphavantage.co"
		self._protocol = protocol
		self._base_url = "/"

		self.__api_key = api_key

		# REST API
		self._session = None
		self._timeout = 7   
		self._retries = 0  # initialize counter
		
		self._max_call_per_min = 5   # default free account
		self._max_call_per_day = 500

		self._last_updates = {}

	def connect(self):
		if self._session is None:
			self._session = requests.Session()

			self._session.headers.update({'user-agent': 'siis-' + '0.2'})
			self._session.headers.update({'content-type': 'application/text'})

	@property
	def connected(self):
		return self._session is not None

	def disconnect(self):
		if self._session:
			self._session = None

	@property
	def authenticated(self):
		# there is no authentication process, only an API key for each GET call.
		return self.__api_key is not None

	def request(self, path, query=None, postdict=None, verb=None, timeout=None, max_retries=None):
		url = self._protocol + self._host + self._base_url + path
		auth = None

		if timeout is None:
			timeout = self._timeout

		# default to POST if data is attached, GET otherwise
		if not verb:
			verb = 'POST' if postdict else 'GET'

		if max_retries is None:
			max_retries = 0 if verb in ['POST', 'PUT'] else 3

		def retry():
			self._retries += 1
			if self._retries > max_retries:
				raise Exception("Max retries on %s (%s) hit, raising." % (path, json.dumps(postdict or '')))

			return self.request(path, query, postdict, timeout, verb, max_retries)

		# Make the request
		response = None
		try:
			logger.debug("Sending req to %s: %s" % (url, json.dumps(postdict or query or '')))

			req = requests.Request(verb, url, json=postdict, auth=auth, params=query)
			prepped = self._session.prepare_request(req)
			response = self._session.send(prepped, timeout=timeout)
			# Make non-200s throw
			response.raise_for_status()

		except requests.exceptions.HTTPError as e:
			if response is None:
				raise e

			# 401 - Auth error. This is fatal.
			if response.status_code == 401:
				logger.error("API Key or Secret incorrect, please check and restart.")
				logger.error("Error: " + response.text, True)
			
				if postdict:
					# fatal error...
					return False

			# 404, can be thrown if order canceled or does not exist.
			elif response.status_code == 404:
				if verb == 'DELETE':
					logger.error("Unable to contact the AlphaVantage API (404). ")
					logger.error("Request: %s \n %s" % (url, json.dumps(postdict)))
					raise e

			# 429, ratelimit; cancel orders & wait until X-RateLimit-Reset
			elif response.status_code == 429:
				logger.error("Ratelimited on current request. ")
				logger.error("Request: %s \n %s" % (url, json.dumps(postdict)))

				to_sleep = 1.0
				# # Figure out how long we need to wait.
				# ratelimit_reset = response.headers['X-RateLimit-Reset']
				# to_sleep = int(ratelimit_reset) - int(time.time()) + 1.0  # add 1.0 more second be we still have issues
				# reset_str = datetime.fromtimestamp(int(ratelimit_reset)).strftime('%X')

				# logger.info("Your ratelimit will reset at %s. Sleeping for %d seconds." % (reset_str, to_sleep))
				time.sleep(to_sleep)

				# Retry the request
				return retry()

			# 503 - temporary downtime, likely due to a deploy. Try again
			elif response.status_code == 503:
				logger.warning("Unable to contact the AlphaVantage API (503), retrying.")
				logger.warning("Request: %s \n %s" % (url, json.dumps(postdict)))

				time.sleep(5)

				return retry()

			elif response.status_code == 400:
				error = response.json()['error']
				message = error['message'].lower() if error else ''

				# If we haven't returned or re-raised yet, we get here.
				logger.error("AlphaVantage unhandled Error: %s: %s" % (e, response.text))
				logger.error("Endpoint was: %s %s: %s" % (verb, path, json.dumps(postdict)))

				raise e

		except requests.exceptions.Timeout as e:
			# Timeout, re-run this request (retry immediately)
			logger.warning("Timed out on request: %s (%s), retrying..." % (path, json.dumps(postdict or '')))
			return retry()

		except requests.exceptions.ConnectionError as e:
			logger.warning("Unable to contact the AlphaVantage API (%s). Please check the URL. Retrying. ")
			logger.warning("Request: %s %s \n %s" % (e, url, json.dumps(postdict)))

			time.sleep(2)
			return retry()

		# Reset retry counter on success
		self._retries = 0

		return response.content  # .json()

	def fetch_stock(self, symbol, tf):
		params = {
			'symbol': symbol,
			'datatype': 'csv',
			'apikey': self.__api_key
		}

		if tf == Instrument.TF_MONTH:
			params['function'] = 'TIME_SERIES_MONTHLY'
		elif tf == Instrument.TF_WEEK:
			params['function'] = 'TIME_SERIES_WEEKLY'
		elif tf == Instrument.TF_DAY:
			params['function'] = 'TIME_SERIES_DAILY'
		elif tf <= Instrument.TF_DAY and tf in self.INTRADAY_TF_MAP:
			params['function'] = 'TIME_SERIES_INTRADAY'
			params['interval'] = self.INTRADAY_TF_MAP[tf]

		endpoint = "/query" # ?" + '&'.join(params)
		result = self.request(query=params, path=endpoint, verb='GET')

		self._last_updates[symbol] = time.time()

		data = []

		# timestamp,open,high,low,close,volume
		rows = result.decode('utf8').split('\n')
		for r in range(1, len(rows)):
			d = rows[r].rstrip('\r').split(',')
			if d and len(d) == 6:
				data.append((self.parse_datetime(d[0]), d[1], d[2], d[3], d[4], d[1], d[2], d[3], d[4], d[5]))

		return data

	def fetch_forex(self, asset, quote, tf):
		params = {
			'from_symbol': asset,
			'to_symbol': quote,
			'datatype': 'csv',
			'apikey': self.__api_key
		}

		if tf == Instrument.TF_MONTH:
			params['function'] = '=FX_MONTHLY'
		elif tf == Instrument.TF_WEEK:
			params['function'] = 'FX_WEEKLY'
		elif tf == Instrument.TF_DAY:
			params['function'] = 'FX_DAILY'
		elif tf <= Instrument.TF_DAY and tf in self.INTRADAY_TF_MAP:
			params['function'] = 'FX_INTRADAY'
			params['interval'] = self.INTRADAY_TF_MAP[tf]

		endpoint = "/query?" + '&'.join(params)
		result = self.request(query=params,path=endpoint, verb='GET')

		self._last_updates[asset+quote] = time.time()

		data = []

		# timestamp,open,high,low,close,volume
		rows = result.decode('utf8').split('\n')
		for r in range(1, len(rows)):
			d = rows[r].rstrip('\r').split(',')
			if d and len(d) == 6:
				data.append((self.parse_datetime(d[0]), d[1], d[2], d[3], d[4], d[1], d[2], d[3], d[4], d[5]))

		return data

	def fetch_crypto(self, asset, quote, tf):
		params = {
			'symbol': asset,
			'market': quote,
			'datatype': 'csv',
			'apikey': self.__api_key
		}		

		if tf == Instrument.TF_MONTH:
			params['function'] = 'DIGITAL_CURRENCY_MONTHLY'
		elif tf == Instrument.TF_WEEK:
			params['function'] = 'DIGITAL_CURRENCY_WEEKLY'
		elif tf == Instrument.TF_DAY:
			params['function'] = 'DIGITAL_CURRENCY_DAILY'

		endpoint = "/query?" + '&'.join(params)
		result = self.request(query=params,path=endpoint, verb='GET')

		self._last_updates[asset+quote] = time.time()

		data = []

		# timestamp,open,high,low,close,volume
		rows = result.decode('utf8').split('\n')
		for r in range(1, len(rows)):
			d = rows[r].rstrip('\r').split(',')
			if d and len(d) == 6:
				data.append((self.parse_datetime(d[0]), d[1], d[2], d[3], d[4], d[1], d[2], d[3], d[4], d[5]))

		return data

	def parse_datetime(self, ts):
		if ' ' in ts:
			return int(datetime.strptime(ts, '%Y-%m-%d %H:%M:%S').replace(tzinfo=UTC()).timestamp()*1000)
		else:
			return int(datetime.strptime(ts, '%Y-%m-%d').replace(tzinfo=UTC()).timestamp()*1000)
