# @date 2022-03-10
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Strategy trade for margin with an indivisible (unique) position and 3 take-profits

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from trader.trader import Trader
    from instrument.instrument import Instrument
    from strategy.strategytrader import StrategyTrader
    from strategy.strategytradercontext import StrategyTraderContextBuilder

from common.signal import Signal
from trader.order import Order

from .strategytrade import StrategyTrade

import logging
logger = logging.getLogger('siis.strategy.indmargin3xtrade')
error_logger = logging.getLogger('siis.error.strategy.indmargin3xtrade')


class StrategyIndMargin3xTrade(StrategyTrade):
    pass
