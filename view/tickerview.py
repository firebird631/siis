# @date 2019-06-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Ticker view.

from view.tableview import TableView
from trader.helpers.markettickertable import markets_tickers_table

import logging
error_logger = logging.getLogger('siis.view.ticker')


class TickerView(TableView):
    """
    Ticker view.
    """

    def __init__(self, service, trader_service):
        super().__init__("ticker", service)

        self._trader_service = trader_service
        self._last_update = 0.0

    def count_items(self):
        if not self._trader_service:
            return 0

        return 1

    def refresh(self):
        if not self._trader_service:
            return

        trader = self._trader_service.trader()
        if trader:
            num = 0

            try:
                columns, table, total_size = markets_tickers_table(
                    trader, *self.table_format(), prev_timestamp=self._last_update,
                    group=self._group, ordering=self._ordering)

                self.table(columns, table, total_size)
                num = total_size[1]
                self._last_update = trader.timestamp
            except Exception as e:
                error_logger.error(str(e))

            # display options
            display_opts = []
            if self._group:
                display_opts.append("Group")
            if self._ordering:
                display_opts.append("Desc.")
            else:
                display_opts.append("Asc.")

            self.set_title("[Tickers %i] %s::%s <%s>" % (
                num, trader.name, trader.account.name, " - ".join(display_opts)))
        else:
            self.set_title("[Tickers 0] No configured trader <>")
