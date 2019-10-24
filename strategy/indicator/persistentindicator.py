# @date 2019-10-22
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Indicator with DB persistance support.

from .indicator import Indicator


class PersistentIndicator(Indicator):
    """
    Base class for a persistent indicator.
    """

    # __slots__ = ''

    @classmethod
    def persistent(cls):
        return True

    @classmethod
    def table(cls):
        return  "indicator_%s" % self._name

    def __init__(self, name, timeframe):
        super().__init__(name, timeframe)
