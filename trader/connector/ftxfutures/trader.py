# @date 2022-09-12
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Trader connector for ftx.com futures

from __future__ import annotations

from typing import TYPE_CHECKING, List, Union, Optional, Tuple

if TYPE_CHECKING:
    from trader.service import TraderService
    from trader.position import Position
    from instrument.instrument import Instrument
    from watcher.connector.ftxfutures.watcher import FTXFuturesWatcher

import time
import traceback

from trader.trader import Trader


class FTXFuturesTrader(Trader):
    """
    @todo
    """
    pass
