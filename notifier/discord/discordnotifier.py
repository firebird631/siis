# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Discord notification handler

import logging
import time
import traceback
import re

from importlib import import_module
from datetime import datetime, timedelta

from notifier.notifier import Notifier

from config import utils

from trader.position import Position
from notifier.discord.webhooks import send_to_discord

from common.signal import Signal

from common.utils import timeframe_to_str

from strategy.helpers.activetradetable import trades_stats_table

import logging
logger = logging.getLogger('siis.notifier.discord')
error_logger = logging.getLogger('siis.error.notifier.discord')


class DiscordNotifier(Notifier):
    """
    Discord notifier for webhooks.
    @todo Active and history tables but this will need at least a timer or usage of API to delete the previous table.
    @todo Strategey alert notifications
    """

    def __init__(self, identifier, service, options):
        super().__init__("discord", identifier, service)

        self._url_re = re.compile(
                r'^(?:http|ftp)s?://' # http:// or https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
                r'localhost|' #localhost...
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
                r'(?::\d+)?' # optional port
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        self._backtesting = options.get('backtesting', False)

        notifier_config = service.notifier_config(identifier)

        self._who = notifier_config.get('who', 'SiiS')
        self._webhooks = notifier_config.get('webhooks', {})

        self._display_percent = False
        self._active_trades = notifier_config.get('active-trades', False)
        self._historical_trades = notifier_config.get('historical-trades', False)

        self._signals_opts = notifier_config.get('signals', (
                "alert",
                "entry",
                "exit",
                # "take-profit",
                # "stop-loss",
                # "quantity",
            ))

        self._strategy_service = None

    def start(self, options):
        if self._backtesting:
            logger.warning("Notifier %s - %s : signals not started because of backtesting !" % (self.name, self.identifier))
            return False
        elif self._webhooks.get('signals'):
            # only of signals webhook is defined

            # could validate url format
            for k, url in self._webhooks.items():
                if re.match(self._url_re, url) is None:
                    raise NotifierException(self.name, self.identifier, "Malformed webhook url %s" % url)

            logger.info("Notifier %s - %s : signals webhook found and valid, start it..." % (self.name, self.identifier))
            return super().start(options)
        else:
            logger.warning("Notifier %s - %s : signals webhook not found, not started !" % (self.name, self.identifier))
            return False

    def terminate(self):
        pass

    def notify(self):
        pass

    def process_signal(self, signal):
        label = ""
        message = ""

        if Signal.SIGNAL_STRATEGY_SIGNAL_ENTRY <= signal.signal_type <= Signal.SIGNAL_STRATEGY_TRADE_UPDATE:
            if signal.data['way'] not in self._signals_opts:
                return

            # generic signal reason
            action = signal.data['way']

            # specified exit reason
            if action == "exit" and 'stats' in signal.data and 'exit-reason' in signal.data['stats']:
                action = signal.data['stats']['exit-reason']

            ldatetime = datetime.fromtimestamp(signal.data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            label = "Signal %s %s on %s" % (action, signal.data['direction'], signal.data['symbol'],)

            ldatetime = datetime.fromtimestamp(signal.data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')

            message = "%s@%s (%s) %s %s at %s - #%s in %s" % (
                signal.data['symbol'],
                signal.data['order-price'],
                signal.data['app-name'],
                action,
                signal.data['direction'],
                ldatetime,
                signal.data['id'],
                signal.data['timeframe'])

            if signal.data.get('stop-loss-price') and 'stop-loss' in self._signals_opts:
                message += " SL@%s" % (signal.data['stop-loss-price'],)

            if signal.data.get('take-profit-price') and 'take-profit' in self._signals_opts:
                message += " TP@%s" % (signal.data['take-profit-price'],)

            if signal.data.get('profit-loss-pct') is not None:
                message += " (%.2f%%)" % (signal.data['profit-loss-pct'],)

            if signal.data.get('order-qty') is not None and 'order-qty' in self._signals_opts:
                message += " Q:%s" % signal.data['order-qty']

            if signal.data.get('label') is not None:
                message += " (%s)" % signal.data['label']

        elif signal.signal_type == Signal.SIGNAL_STRATEGY_ALERT:
            if 'alert' not in self._signals_opts:
                return

            # detailed alert reason
            reason = signal.data['reason']

            if signal.data['trigger'] > 0:
                border = "green"
            elif signal.data['trigger'] < 0:
                border = "orange"
            else:
                border = "default"

            ldatetime = datetime.fromtimestamp(signal.data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            label = "Alert %s %s on %s" % (signal.data['name'], signal.data['reason'], signal.data['symbol'],)

            ldatetime = datetime.fromtimestamp(signal.data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')

            message = "%s %s@%s (%s) %s at %s - #%s in %s" % (
                signal.data['name'],
                signal.data['symbol'],
                signal.data['last-price'],
                signal.data['app-name'],
                signal.data['reason'],
                ldatetime,
                signal.data['id'],
                signal.data['timeframe'])

            if signal.data.get('user') is not None:
                message += " (%s)" % signal.data['user']

        elif signal.signal_type == Signal.SIGNAL_MARKET_SIGNAL:
            return

        if message:
            dst = self._webhooks.get('signals')
            if dst:
                try:
                    send_to_discord(dst, self._who, '```' + message + '```')
                except:
                    pass

    def command(self, command_type, data):
        pass

    def receiver(self, signal):
        if not self._playpause or self._backtesting or not signal:
            return

        if signal.source == Signal.SOURCE_STRATEGY:
            if Signal.SIGNAL_STRATEGY_SIGNAL_ENTRY <= signal.signal_type <= Signal.SIGNAL_STRATEGY_ALERT:
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

    #         if strategy.identifier + '.trades' in self._discord_webhooks:
    #             trades_dst = self._discord_webhooks[strategy.identifier + '.trades']

    #         if strategy.identifier + '.agg-trades' in self._discord_webhooks:
    #             agg_trades_dst = self._discord_webhooks[strategy.identifier + '.agg-trades']

    #         if strategy.identifier + '.closed-trades' in self._discord_webhooks:
    #             closed_trades_dst = self._discord_webhooks[strategy.identifier + '.closed-trades']

    #         if trades_dst:
    #             columns, table, total_size = trades_stats_table(appl, *Terminal.inst().active_content().format(), quantities=True, percents=True)
    #             if table:
    #                 arr = self.format_table(table)
    #                 self.split_and_send(trades_dst, arr)
            
    #         if agg_trades_dst:
    #             columns, table, total_size = agg_trades_stats_table(appl, *Terminal.inst().active_content().format(), quantities=True)
    #             if table:
    #                 arr = self.format_table(table)
    #                 self.split_and_send(agg_trades_dst, arr)

    #         if closed_trades_dst:
    #             columns, table, total_size = closed_trades_stats_table(appl, *Terminal.inst().active_content().format(), quantities=True, percents=True)
    #             if table:
    #                 arr = self.format_table(table)
    #                 self.split_and_send(closed_trades_dst, arr)

    #     return True
