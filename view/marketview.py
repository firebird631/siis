# @date 2019-06-28
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Market view.

from terminal.terminal import Terminal
from view.tableview import TableView

import logging
error_logger = logging.getLogger('siis.view.market')


class MarketView(TableView):
    """
    Market info view.
    """

    def __init__(self, service, trader_service):
        super().__init__("market", service)

        self._trader_service = trader_service

    def count_items(self):
        if not self._trader_service:
            return 0

        return(self._trader_service.get_traders())

    def refresh(self):
        if not self._trader_service:
            return

        traders = self._trader_service.get_traders()
        if len(traders) > 0 and -1 < self._item < len(traders):
            trader = traders[self._item]
            num = 0

            try:
                columns, table, total_size = trader.markets_table(*self.table_format())
                self.table(columns, table, total_size)
                num = total_size[1]
            except Exception as e:
                error_logger.error(str(e))

            self.set_title("Market info list (%i) trader %s on account %s" % (num, trader.name, trader.account.name))
        else:
            self.set_title("Market info list - No configured trader")
