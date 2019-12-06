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

    MODE_NONE = 0
    MODE_SIGNAL = 1
    MODE_TRADE = 2

    MODE = {
        'disabled': MODE_NONE,
        'none': MODE_NONE,
        'signal': MODE_SIGNAL,
        'enabled': MODE_TRADE,
        'trade': MODE_TRADE
    }

    def __init__(self):
        pass

    def dumps(self):
        return {}

    def loads(self, data):
        pass
