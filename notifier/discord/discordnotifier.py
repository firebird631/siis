# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Discord notification handler

import time
import logging
import traceback

from importlib import import_module
from datetime import datetime, timedelta

from notifier.notifier import Notifier

from config import utils

from trader.position import Position
from notifier.discord.webhooks import send_to_discord

from common.signal import Signal

from common.utils import timeframe_to_str

import logging
logger = logging.getLogger('siis.notifier.discord')
error_logger = logging.getLogger('siis.error.notifier.discord')


class DiscordNotifier(Notifier):
    """
    Discord notifier for webhooks.
    @todo Active and history tables but this will need at least a timer or usage of API to delete the previous table.
    """

    def __init__(self, name, identifier, service, options):
        super().__init__("discord", identifier, service)

        self._backtesting = options.get('backtesting', False)

        notifier_config = service.notifier_config(name)

        self._display_percents = False

        self._who = notifier_config.get('who', 'SiiS')
        self._webhooks = notifier_config.get('webhooks', {})

        # @todo could validate url format

        self._send_active_trades = notifier_config.get('active-trades', False)
        self._send_historical_trades = notifier_config.get('historical-trades', False)

        self._strategy_service = None

    def start(self, options):
        if self._webhooks.get('signals') and not self._backtesting:
            # only of signals webhook is defined
            return super().start(options)
        else:
            return False

    def terminate(self):
        pass

    def notify(self):
        pass

    def update(self):
        count = 0

        while self._signals:
            signal = self._signals.popleft()

            label = ""
            message = ""

            if signal.signal_type == Signal.SIGNAL_STRATEGY_ENTRY_EXIT:
                direction = "long" if signal.data['direction'] == Position.LONG else "short"
                ldatetime = datetime.fromtimestamp(signal.data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                label = "Signal %s %s on %s" % (signal.data['action'], direction, signal.data['symbol'],)

                message = "%s@%s (%s) %s %s at %s - #%s in %s" % (
                    signal.data['symbol'],
                    signal.data['price'],
                    signal.data['trader-name'],
                    signal.data['action'],
                    direction,
                    ldatetime,
                    signal.data['trade-id'],
                    timeframe_to_str(signal.data['timeframe']))

                if signal.data['stop-loss']:
                    message += " SL@%s" % (signal.data['stop-loss'],)

                if signal.data['take-profit']:
                    message += " TP@%s" % (signal.data['take-profit'],)

                if signal.data['profit-loss'] is not None:
                    message += " (%.2f%%)" % ((signal.data['profit-loss'] * 100),)

                if signal.data['comment'] is not None:
                    message += " (%s)" % signal.data['comment']

            elif signal.signal_type == Signal.SIGNAL_STRATEGY_SIGNAL:
                pass

            elif signal.signal_type == Signal.SIGNAL_MARKET_SIGNAL:
                pass

            if message:
                dst = self._webhooks.get('signals')
                if dst:
                    try:
                        send_to_discord(dst, self._who, '```' + message + '```')
                    except:
                        pass

            count += 1
            if count > 10:
                # no more than per loop
                break

        return True

    def command(self, command_type, data):
        pass

    def receiver(self, signal):
        if not self._playpause or self._backtesting or not signal:
            return

        if signal.source == Signal.SOURCE_STRATEGY:
            if signal.signal_type in (Signal.SIGNAL_SOCIAL_ENTER, Signal.SIGNAL_SOCIAL_EXIT, Signal.SIGNAL_STRATEGY_ENTRY_EXIT):
                self.push_signal(signal)

    #
    # helpers
    #

    def split_and_send(self, dst, msg):
        MAX_MSG_SIZE = 2000 - 6 - 25

        rows = msg.split('\n')
        i = 0

        while i < len(rows):
            buf = ""

            while (i < len(rows)) and (len(buf) + len(rows[i]) + 1 < MAX_MSG_SIZE):
                buf += rows[i] + '\n'
                i += 1

            if buf:
                send_to_discord(dst, self._who, '```' + buf + '```')

    def format_table(self, data):
        arr = tabulate(data, headers='keys', tablefmt='psql', showindex=False, floatfmt=".2f", disable_numparse=True)
        # remove colors
        arr = arr.replace(Color.ORANGE, '').replace(Color.RED, '').replace(Color.GREEN, '').replace(Color.WHITE, '').replace(Color.PURPLE, '')

        return arr

    # def send_tables(self):
    #     for strategy in self.strategy_service.get_appliances():
    #         dst = None

    #         if strategy.identifier + '.trades' in self._discord_webhook:
    #             trades_dst = self._discord_webhook[strategy.identifier + '.trades']

    #         if strategy.identifier + '.agg-trades' in self._discord_webhook:
    #             agg_trades_dst = self._discord_webhook[strategy.identifier + '.agg-trades']

    #         if strategy.identifier + '.closed-trades' in self._discord_webhook:
    #             closed_trades_dst = self._discord_webhook[strategy.identifier + '.closed-trades']

    #         if trades_dst:
    #             columns, table, total_size = appl.trades_stats_table(*Terminal.inst().active_content().format(), quantities=True, percents=True)
    #             if table:
    #                 arr = self.format_table(table)
    #                 self.split_and_send(trades_dst, arr)
            
    #         if agg_trades_dst:
    #             columns, table, total_size = appl.agg_trades_stats_table(*Terminal.inst().active_content().format(), quantities=True)
    #             if table:
    #                 arr = self.format_table(table)
    #                 self.split_and_send(agg_trades_dst, arr)

    #         if closed_trades_dst:
    #             columns, table, total_size = appl.closed_trades_stats_table(*Terminal.inst().active_content().format(), quantities=True, percents=True)
    #             if table:
    #                 arr = self.format_table(table)
    #                 self.split_and_send(closed_trades_dst, arr)

    #     return True
