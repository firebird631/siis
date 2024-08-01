# @date 2021-10-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# Strategy shared or local handler.

from __future__ import annotations

from typing import TYPE_CHECKING, Union, Dict, List, Set, Optional

if TYPE_CHECKING:
    from strategy.strategytraderbase import StrategyTraderBase
    from strategy.trade.strategytrade import StrategyTrade

import threading

import logging
logger = logging.getLogger('siis.strategy.handler')
error_logger = logging.getLogger('siis.error.strategy.handler')
traceback_logger = logging.getLogger('siis.traceback.strategy.handler')


class Handler(object):
    """
    Strategy trader shared or local handler base class.
    """

    NAME = "undefined"

    _context_id: str
    _mutex: threading.RLock
    _installed_strategy_traders: List[StrategyTraderBase]
    _need_update: Set[StrategyTraderBase]

    def __init__(self, context_id: str):
        self._context_id = context_id

        self._mutex = threading.RLock()

        self._installed_strategy_traders = []
        self._need_update = set()

    @classmethod
    def name(cls) -> str:
        """
        String type name of the handler.
        """
        return cls.NAME

    #
    # slots
    #

    def on_trade_opened(self, strategy_trader: StrategyTraderBase, trade: StrategyTrade):
        """
        Called when a trade is added.
        """
        pass

    def on_trade_updated(self, strategy_trader: StrategyTraderBase, trade: StrategyTrade):
        """
        Called when a trade is updated (execution, modification).
        """
        pass

    def on_trade_exited(self, strategy_trader: StrategyTraderBase, trade: StrategyTrade):
        """
        Called when a trade is remove (closed or canceled).
        """
        pass

    #
    # setup
    #

    def install(self, strategy_trader: StrategyTraderBase):
        pass

    def uninstall(self, strategy_trader: StrategyTraderBase):
        pass

    @property
    def context_id(self) -> str:
        return self._context_id

    #
    # process
    #

    def process(self, strategy_trader: StrategyTraderBase):
        pass

    def is_related(self, trade: StrategyTrade):
        if self._context_id:
            # if a context is defined must match
            return trade is not None and trade.context is not None and trade.context.name == self._context_id

        # else always return True
        return trade is not None

    #
    # report
    #

    def report(self, strategy_trader: StrategyTraderBase) -> Dict[str, Union[str, int, float]]:
        """Dumps for persistence, communication or for display information"""
        return {
            'Handler': self.name(),
            'Context': self._context_id or "Global"
        }

    #
    # persistence / report
    #

    def dumps(self, strategy_trader: StrategyTraderBase) -> Dict[str, Union[str, int, float]]:
        """Dumps for persistence, communication or for debug"""
        return {
            'name': self.name(),
            'context': self._context_id
        }

    def loads(self, data: dict):
        """Load from previous dumps"""
        if self.name != data.get('name', ""):
            return

        self._context_id = data.get('context', "")
