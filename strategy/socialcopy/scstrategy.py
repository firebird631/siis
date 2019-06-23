# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Simple social copy strategy

import time
import datetime 

from terminal.terminal import Terminal

from config import config
from strategy.strategy import Strategy


class SocialCopyStrategy(Strategy):
    """
    Simple social copy strategy.
    @todo move here all the rest here...
    """

    POLICY_COPY_EVERYWHERE = 0       # copy to from any watcher to any trader (as possible symbols)
    POLICY_COPY_SAME_AS_ORIGIN = 1   # copy only from a watcher type to the same trader type

    MAX_COPY_ENTRY_DELAY = 5*60      # filters social trades only lesser than N seconds (5 min)
    MAX_ORDER_COPY_SLIPPAGE = 60     # filters strategy signals only lesser than N seconds (@todo take care must be lasser than Trader.PURGE_COMMANDS_DELAY)

    def __init__(self, strategy_service, watcher_service, trader_service, options):
        super().__init__("socialcopy", strategy_service, watcher_service, trader_service, options)

        self._flags = Strategy.SUPPORT_LIVE

    def start(self):
        if super().start():
            return True
        else:
            return False

    def pause(self):
        super().pause()

    def stop(self):
        super().stop()

    def update_strategy(self, tf, instrument):
        pass
