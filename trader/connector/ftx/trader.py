# @date 2022-09-12
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Trader connector for ftx.com

from __future__ import annotations

from typing import TYPE_CHECKING, List, Union, Optional, Tuple

if TYPE_CHECKING:
    from trader.service import TraderService
    from trader.position import Position
    from instrument.instrument import Instrument
    from watcher.connector.ftx.watcher import FTXWatcher

import time
import traceback

from trader.trader import Trader


class FTXTrader(Trader):
    """
    @todo
    """
    pass
