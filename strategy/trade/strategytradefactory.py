# @date 2021-03-10
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Strategy trade class factory

from .strategyassettrade import StrategyAssetTrade
from .strategyindmargin3xtrade import StrategyIndMargin3xTrade
from .strategyindmargintrade import StrategyIndMarginTrade
from .strategymargintrade import StrategyMarginTrade
from .strategypositiontrade import StrategyPositionTrade

import logging
logger = logging.getLogger('siis.strategy.trade.factory')


class StrategyTradeFactory(object):
    """
    Strategy class factory.
    """

    @classmethod
    def clazz(cls, name):
        if name == "StrategyAssetTrade":
            return StrategyAssetTrade
        elif name == "StrategyMarginTrade":
            return StrategyMarginTrade
        elif name == "StrategyIndMarginTrade":
            return StrategyIndMarginTrade
        elif name == "StrategyPositionTrade":
            return StrategyPositionTrade
        elif name == "StrategyIndMargin3xTrade":
            return StrategyIndMargin3xTrade
        elif name == "asset":
            return StrategyAssetTrade
        elif name == "margin":
            return StrategyMarginTrade
        elif name == "ind-margin":
            return StrategyIndMarginTrade
        elif name == "position":
            return StrategyPositionTrade
        elif name == "ind-margin-3x":
            return StrategyIndMargin3xTrade

        return None

    @classmethod
    def instance(cls, name, timeframe):
        Clazz = cls.clazz(name)
        if Clazz is not None:
            return Clazz(timeframe)

        return None
