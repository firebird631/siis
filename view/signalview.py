# @date 2019-06-28
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Signal view.

import threading
import hashlib

from datetime import datetime

from common.utils import timeframe_to_str
from common.signal import Signal

from terminal.terminal import Terminal, Color
from terminal import charmap

from view.tableview import TableView

import logging
logger = logging.getLogger('siis.view.signal')
error_logger = logging.getLogger('siis.error.view.signal')


class SignalView(TableView):
    """
    Signal view.
    """

    REFRESH_RATE = 60  # only on signal or 1 minute refresh

    MAX_SIGNALS = 200
    COLUMNS = ('#', 'Market', 'Type', charmap.ARROWUPDN, 'TF', 'EP', 'SL', 'TP', 'Date', 'Comment', 'P/L')

    def __init__(self, service, strategy_service):
        super().__init__("signal", service)

        self._mutex = threading.RLock()
        self._strategy_service = strategy_service
        self._signals_list = {}

        # listen to its service
        self.service.add_listener(self)

    def count_items(self):
        if not self._strategy_service:
            return 0

        return(self._strategy_service.get_traders())

    def receiver(self, signal):
        if not signal:
            return

        if signal.source == Signal.SOURCE_STRATEGY:
            if signal.signal_type in (Signal.SIGNAL_STRATEGY_SIGNAL, Signal.SIGNAL_STRATEGY_ENTRY, Signal.SIGNAL_STRATEGY_EXIT):
                with self._mutex:
                    if signal.data.get('identifier'):
                        if signal.data['identifier'] not in self._signals_list:
                            self._signals_list[signal.data['identifier']] = []

                        signals_list = self._signals_list[signal.data['identifier']]
                        signals_list.append(signal.data)

                        if len(signals_list) > SignalView.MAX_SIGNALS:
                            signals_list.pop(0)

                        self._refresh = 0.0

    def signals_table(self, appliance, style='', offset=None, limit=None, col_ofs=None):
        data = []

        signals = self._signals_list.get(appliance.identifier, [])
        total_size = (len(SignalView.COLUMNS), len(signals))

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(signals)

        limit = offset + limit

        if self._group:
            signals.sort(key=lambda x: -x['timestamp'] and -x['trade-id'])
        else:
            signals.sort(key=lambda x: -x['timestamp'])

        signals = signals[offset:limit]

        for signal in signals:
            ldatetime = datetime.fromtimestamp(signal['timestamp']).strftime(self._datetime_format)
            direction = Color.colorize_cond(charmap.ARROWUP if signal['direction'] > 0 else charmap.ARROWDN,
                    signal['direction'] > 0, style, true=Color.GREEN, false=Color.RED)

            symbol_color = int(hashlib.sha1(signal['symbol'].encode("utf-8")).hexdigest(), 16) % Color.count()-1
            id_color = signal['trade-id'] % Color.count()-1

            lid = Color.colorize(str(signal['trade-id']), Color.color(id_color), style)
            lsymbol = Color.colorize(signal['symbol'], Color.color(symbol_color), style)

            row = (
                lid,
                lsymbol,
                signal['action'],
                direction,
                timeframe_to_str(signal['timeframe']),
                signal['price'],
                signal['stop-loss'],
                signal['take-profit'],
                ldatetime,
                signal['comment'],
                " (%.2f%%)" % ((signal['profit-loss'] * 100),) if signal['profit-loss'] is not None else ""
            )

            data.append(row[col_ofs:])

        return SignalView.COLUMNS[col_ofs:], data, total_size

    def refresh(self):
        if not self._strategy_service:
            return

        appliances = self._strategy_service.get_appliances()
        if len(appliances) > 0 and -1 < self._item < len(appliances):
            appliance = appliances[self._item]
            num = 0

            with self._mutex:
                try:
                    columns, table, total_size = self.signals_table(appliance, *self.table_format())
                    self.table(columns, table, total_size)
                    num = total_size[1]
                except Exception as e:
                    error_logger.error(str(e))

            self.set_title("Signal list (%i) for strategy %s - %s" % (num, appliance.name, appliance.identifier))
        else:
            self.set_title("Signal list - No configured strategy")
