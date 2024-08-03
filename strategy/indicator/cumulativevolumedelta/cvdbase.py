# @date 2024-07-28
# @author Frederic Scherma
# @license Copyright (c) 2024 Dream Overflow
# Cumulative Volume Delta indicator

from strategy.indicator.indicator import Indicator


class CumulativeVolumeDeltaBase(Indicator):
    """
    Base model for cumulative volume delta indicator.

    # @todo Support of evening session and overnight session.
    """

    # __slots__ =

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_VOLUME

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_CUMULATIVE

    @classmethod
    def builder(cls, base_type: int, timeframe: float, **kwargs):
        """
        Default class builder. Base type use to distinct the type of instance (tick, tickbar, timeframe...)
        @param base_type: One of BASE_TIMEFRAME, BASE_TICK, BASE_TICKBAR
        @param timeframe: Timeframe in second or 0 if none.
        @param kwargs: Args given to indicator __init__
        @return: A new instance of the indicator
        """
        if base_type == Indicator.BASE_TIMEFRAME:
            from strategy.indicator.cumulativevolumedelta.barcvd import BarCumulativeVolumeDelta
            return BarCumulativeVolumeDelta(timeframe, **kwargs)
        elif base_type == Indicator.BASE_TICKBAR:
            from strategy.indicator.cumulativevolumedelta.barcvd import BarCumulativeVolumeDelta
            return BarCumulativeVolumeDelta(timeframe, **kwargs)
        elif base_type == Indicator.BASE_TICK:
            from strategy.indicator.cumulativevolumedelta.cvd import CumulativeVolumeDelta
            return CumulativeVolumeDelta(timeframe, **kwargs)

        return None

    def __init__(self, name: str, timeframe: float, session):
        super().__init__(name, timeframe)
