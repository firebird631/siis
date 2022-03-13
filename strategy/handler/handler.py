# @date 2021-10-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# Strategy shared or local handler.

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

    def __init__(self, context_id):
        self._context_id = context_id

        self._mutex = threading.RLock()

        self._installed_strategy_traders = []
        self._need_update = set()

    @classmethod
    def name(cls):
        """
        String type name of the handler.
        """
        return cls.NAME

    #
    # slots
    #

    def on_trade_opened(self, strategy_trader, trade):
        """
        Called when a trade is added.
        """
        pass

    def on_trade_exited(self, strategy_trader, trade):
        """
        Called when a trade is remove (closed or canceled).
        """
        pass

    #
    # setup
    #

    def install(self, strategy_trader):
        pass

    def uninstall(self, strategy_trader):
        pass

    @property
    def context_id(self):
        return self._context_id

    #
    # process
    #

    def process(self, strategy_trader):
        pass

    def is_related(self, trade):
        return trade is not None and trade.context is not None and trade.context.name == self._context_id

    #
    # report
    #

    def dumps(self):
        return {
            'name': self.name(),
            'context': self._context_id
        }
