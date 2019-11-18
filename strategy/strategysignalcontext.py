# @date 2019-01-13
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Strategy signal context


class StrategySignalContextBuilder(object):
	"""
	To be implemented by strategy to have specific context trade persistence.
	"""

	@classmethod
	def loads(cls, data):
		return None


class StrategySignalContext(object):
	"""
	Base model for any signal/trade context.
	"""

    def __init__(self):
        pass

    def dumps(self):
        return {}

    def loads(self, data):
        pass
