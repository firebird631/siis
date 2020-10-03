# @date 2019-06-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Historical trades view.

from terminal.terminal import Terminal
from view.tableview import TableView

from common.signal import Signal
from strategy.helpers.closedtradetable import closed_trades_stats_table

import logging
error_logger = logging.getLogger('siis.view.tradehistory')


class TradeHistoryView(TableView):
    """
    Historical trade view.
    # @todo Could use local table and add row from signal data but need more complete signal data
    """

    REFRESH_RATE = 60.0

    def __init__(self, service, strategy_service):
        super().__init__("stats", service)

        self._strategy_service = strategy_service

        # listen to its service
        self.service.add_listener(self)

    def receiver(self, signal):
        if not signal:
            return

        if signal.source == Signal.SOURCE_STRATEGY:
            if signal.signal_type == Signal.SIGNAL_STRATEGY_TRADE_EXIT:
                with self._mutex:
                    if "exit" in signal.data.get('way'):
                        self._refresh = 0.0

    def refresh(self):
        if not self._strategy_service:
            return

        strategy = self._strategy_service.strategy()
        if strategy:
            num = 0

            try:
                columns, table, total_size = closed_trades_stats_table(strategy, *self.table_format(),
                        quantities=True, percents=self._percent, datetime_format=self._datetime_format)

                self.table(columns, table, total_size)
                num = total_size[1]
            except Exception as e:
                error_logger.error(str(e))

            self.set_title("Trade history (%i) for strategy %s - %s" % (num, strategy.name, strategy.identifier))
        else:
            self.set_title("Trade history - No configured strategy")
