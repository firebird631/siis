# @date 2019-06-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Signals view.

import copy
import threading
import hashlib

from datetime import datetime
from typing import List

from common.signal import Signal

from terminal.terminal import Color
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

    MAX_SIGNALS = 500
    COLUMNS = ('#', 'Symbol', charmap.ARROWLR, charmap.ARROWUPDN, 'TF', 'EP', 'SL', 'TP', 'Date', 'Label',
               'Reason', 'P/L')

    def __init__(self, service, strategy_service):
        super().__init__("signal", service)

        self._mutex = threading.RLock()
        self._strategy_service = strategy_service
        self._ordering = True  # initially most recent first

        self._signals_list = []

        # listen to its service
        self.service.add_listener(self)

    def count_items(self):
        if not self._strategy_service:
            return 0

        return 1

    def receiver(self, signal):
        if not signal:
            return

        if signal.source == Signal.SOURCE_STRATEGY:
            # if Signal.SIGNAL_STRATEGY_SIGNAL_ENTRY <= signal.signal_type <= Signal.SIGNAL_STRATEGY_TRADE_UPDATE:
            if Signal.SIGNAL_STRATEGY_SIGNAL_ENTRY <= signal.signal_type <= Signal.SIGNAL_STRATEGY_SIGNAL_EXIT:
                with self._mutex:
                    self._signals_list.append(signal.data)

                    if len(self._signals_list) > SignalView.MAX_SIGNALS:
                        self._signals_list.pop(0)

                    self._refresh = 0.0

    def signals_table(self, strategy, style='', offset=None, limit=None, col_ofs=None):
        """
        Generate the table of signal according to current signal list.
        @note This method is not thread safe.
        @param strategy:
        @param style:
        @param offset:
        @param limit:
        @param col_ofs:
        @return:
        """
        data = []

        signals = self._signals_list
        total_size = (len(SignalView.COLUMNS), len(signals))

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(signals)

        limit = offset + limit

        if self._group:
            signals_entries = []
            signals_exits = []

            for signal in signals:
                if signal['way'] == "entry" or signal['id'] <= 0:
                    signals_entries.append(signal)
                elif signal['way'] == "exit":
                    signals_exits.append(signal)

            signals_entries.sort(key=lambda x: x['timestamp'])
            signals = []

            for signal_entry in signals_entries:
                signals.append(signal_entry)

                # lookup for the related exit
                if signal_entry['id'] > 0:
                    for signal_exit in signals_exits:
                        if (signal_exit['market-id'] == signal_entry['market-id'] and
                                signal_exit['id'] == signal_entry['id']):

                            signals.append(signal_exit)
                            break

            if self._ordering:
                signals.reverse()
        else:
            signals = sorted(signals, key=lambda x: x['timestamp'], reverse=True if self._ordering else False)

        signals = signals[offset:limit]

        for signal in signals:
            ldatetime = datetime.fromtimestamp(signal['timestamp']).strftime(self._datetime_format)
            direction = Color.colorize_cond(charmap.ARROWUP if signal['direction'] == "long" else charmap.ARROWDN,
                                            signal['direction'] == "long", style, true=Color.GREEN, false=Color.RED)

            signal_id = '-'
            id_color = 0

            if signal['id'] > 0:
                signal_id = str(signal['id'])
                id_color = signal['id'] % Color.count()

            symbol_color = int(hashlib.sha1(signal['symbol'].encode("utf-8")).hexdigest(), 16) % Color.count()

            lid = Color.colorize(signal_id, Color.color(id_color), style)
            lsymbol = Color.colorize(signal['symbol'], Color.color(symbol_color), style)

            way = Color.colorize_cond(charmap.ARROWR if signal['way'] == "entry" else charmap.ARROWL,
                                      signal['way'] == "entry", style, true=Color.BLUE, false=Color.ORANGE)

            if signal['way'] == "entry":
                reason = signal['stats'].get('entry-order-type', "") if 'stats' in signal else ""
            elif signal['way'] == "exit":
                reason = signal['stats'].get('exit-reason', "") if 'stats' in signal else ""
            else:
                reason = ""

            row = (
                lid,
                lsymbol,
                way,
                direction,
                signal.get('timeframe', ""),
                signal.get('order-price', ""),
                signal.get('stop-loss-price', ""),
                signal.get('take-profit-price', ""),
                ldatetime,
                signal.get('label', ""),
                reason,
                " (%.2f%%)" % (signal['profit-loss-pct'],) if signal.get('profit-loss-pct') is not None else ""
            )

            data.append(row[0:4] + row[4+col_ofs:])

        return SignalView.COLUMNS[0:4] + SignalView.COLUMNS[4+col_ofs:], data, total_size

    def refresh(self):
        if not self._strategy_service:
            return

        strategy = self._strategy_service.strategy()
        if strategy:
            num = 0

            with self._mutex:
                try:
                    columns, table, total_size = self.signals_table(strategy, *self.table_format())
                    self.table(columns, table, total_size)
                    num = total_size[1]
                except Exception as e:
                    import traceback
                    error_logger.error(str(traceback.format_exc()))
                    error_logger.error(str(e))

            self.set_title("Signal list (%i)%s for strategy %s - %s" % (
                num, self.display_mode_str(), strategy.name, strategy.identifier))
        else:
            self.set_title("Signal list - No configured strategy")

    def dumps_signals(self) -> List[dict]:
        signals = []

        with self._mutex:
            for signal in self._signals_list:
                signals.append(copy.copy(signal))

        return signals
