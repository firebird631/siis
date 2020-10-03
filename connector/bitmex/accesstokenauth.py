# @date 2018-08-23
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# BitMex auth


from requests.auth import AuthBase


class AccessTokenAuth(AuthBase):
	"""Attaches Access Token Authentication to the given Request object."""

	def __init__(self, access_token):
		"""Init with Token."""
		self.token = access_token

	def __call__(self, r):
		"""Called when forming a request - generates access token header."""
		if (self.token):
			r.headers['access-token'] = self.token

		return r
