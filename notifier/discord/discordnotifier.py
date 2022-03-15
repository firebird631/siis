# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Discord notification handler
import copy
import re

from tabulate import tabulate
from datetime import datetime, timedelta

from notifier.notifier import Notifier
from terminal.terminal import Color

from notifier.discord.webhooks import send_to_discord
from notifier.notifierexception import NotifierException

from common.signal import Signal

# from strategy.helpers.activetradetable import trades_stats_table

import logging

from common.utils import timeframe_from_str

logger = logging.getLogger('siis.notifier.discord')
error_logger = logging.getLogger('siis.error.notifier.discord')


class DiscordNotifier(Notifier):
    """
    Discord notifier for webhooks.
    @todo Active and history tables but this will need at least a timer or usage of API to delete the previous table.
    """

    def __init__(self, identifier, service, options):
        super().__init__("discord", identifier, service)

        self._url_re = re.compile(
                r'^(?:http|ftp)s?://'  # http:// or https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
                r'localhost|'  # localhost...
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
                r'(?::\d+)?'  # optional port
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        self._backtesting = options.get('backtesting', False)

        notifier_config = service.notifier_config(identifier)

        self._who = notifier_config.get('who', 'SiiS')
        self._webhooks = notifier_config.get('webhooks', {})
        self._avatar_url = notifier_config.get('avatar-url', None)

        self._display_percent = False
        self._active_trades = notifier_config.get('active-trades', False)
        self._historical_trades = notifier_config.get('historical-trades', False)

        self._template = notifier_config.get('template', "default")

        self._signals_opts = notifier_config.get('signals', (
                "alert",
                "entry",
                "exit",
                # "update",
                # "take-profit",
                # "stop-loss",
                # "quantity",
                # "error",
            ))

        self._strategy_service = None

        self._opened_trades = {}
        self._closed_trades = {}
        self._canceled_trades = {}

    def start(self, options):
        if self._backtesting:
            logger.warning("Notifier %s - %s : signals not started because of backtesting !" % (
                self.name, self.identifier))
            return False

        if self._webhooks.get('signals'):
            # only if signals webhook is defined

            # could validate url format
            for k, url in self._webhooks.items():
                if re.match(self._url_re, url) is None:
                    raise NotifierException(self.name, self.identifier, "Malformed webhook url %s" % url)

            has_signal = True

            logger.info("Notifier %s - %s : signals webhook found and valid, start it..." % (
                self.name, self.identifier))
        else:
            logger.warning("Notifier %s - %s : signals webhook not found, not started !" % (
                self.name, self.identifier))
            return False

        # template
        if self._template not in ("default", "light", "verbose"):
            raise NotifierException(self.name, self.identifier, "Invalid template name %s" % self._template)

        if has_signal:
            return super().start(options)
        else:
            logger.warning("Notifier %s - %s : signals webhook not found, not started !" % (
                self.name, self.identifier))
            return False

    def terminate(self):
        pass

    def notify(self):
        pass

    def format_trade_entry(self, t, locale):
        messages = []

        trade_id = t['id']
        symbol = t['symbol']

        open_dt = Notifier.parse_utc_datetime(t['entry-open-time'])

        op = float(t.get('order-price', "0"))
        aep = float(t.get('avg-entry-price', "0"))

        order_type = t['stats']['entry-order-type']

        if self._template in ("default", "verbose"):
            messages.append("%s %s:%s [ NEW ]" % (t['direction'].capitalize(), symbol, trade_id))
            messages.append("- %s: %s" % (order_type.title(), Notifier.format_datetime(open_dt, locale)))

            if aep:
                messages.append("- Entry-Price: %s" % t['avg-entry-price'])
            elif op:
                messages.append("- Order-Price: %s" % t['order-price'])

            if t['timeframe']:
                messages.append("- Timeframe: %s" % t['timeframe'])

            if t['label']:
                messages.append("- Context: %s" % t['label'])

            if t['entry-timeout'] and not aep:
                # before in position
                et_tf = timeframe_from_str(t['entry-timeout'])
                if et_tf > 0.0:
                    entry_timeout_dt = open_dt + timedelta(seconds=et_tf)
                    messages.append("- Cancel entry after : %s" % Notifier.format_datetime(entry_timeout_dt))

            if t['expiry'] and aep:
                # until in position
                expiry_dt = open_dt + timedelta(seconds=t['expiry'])
                messages.append("- Close expiry after : %s" % Notifier.format_datetime(expiry_dt))

        elif self._template == "light":
            messages.append("%s %s:%s [ NEW ]" % (t['direction'].capitalize(), symbol, trade_id))

            if aep:
                messages.append("- Entry-Price: %s" % t['avg-entry-price'])
            elif op:
                messages.append("- Entry-Price: %s" % t['order-price'])

        if float(t['take-profit-price']):
            messages.append("- Take-Profit: %s" % t['take-profit-price'])
        if float(t['stop-loss-price']):
            messages.append("- Stop-Loss: %s" % t['stop-loss-price'])

        if t['comment']:
            messages.append('- Comment: %s' % t['comment'])

        return messages

    def format_trade_update(self, t, locale):
        messages = []

        trade_id = t['id']
        symbol = t['symbol']

        # filter only if a change occurs on targets or from entry execution state
        pt = self._opened_trades.get(symbol, {}).get(trade_id)

        accept = False
        execute = False
        modify_tp = False
        modify_sl = False
        modify_comment = False

        if pt:
            if pt['avg-entry-price'] != t['avg-entry-price']:
                accept = True
                execute = True
            if pt['take-profit-price'] != t['take-profit-price']:
                accept = True
                modify_tp = True
            if pt['stop-loss-price'] != t['stop-loss-price']:
                accept = True
                modify_sl = True
            if pt['comment'] != t['comment']:
                accept = True
                modify_comment = True

        if accept:
            if self._template in ("default", "verbose"):
                if execute and float(t['avg-entry-price']):
                    messages.append("- Entry-Price: %s" % t['avg-entry-price'])

            if modify_tp and float(t['take-profit-price']):
                messages.append("- Modify-Take-Profit: %s" % t['take-profit-price'])
            if modify_sl and float(t['stop-loss-price']):
                messages.append("- Modify-Stop-Loss: %s" % t['stop-loss-price'])

            if modify_comment and t['comment']:
                messages.append("- Comment: %s" % t['comment'])

            if messages:
                # prepend update message if there is some content to publish
                messages.insert(0, "%s %s:%s [ UPDATE ]" % (t['direction'].capitalize(), symbol, trade_id))

        return messages

    def format_trade_exit(self, t, locale):
        messages = []

        trade_id = t['id']
        symbol = t['symbol']

        axp = float(t.get('avg-exit-price', "0"))

        messages.append("%s %s:%s [ CLOSE ]" % (t['direction'].capitalize(), symbol, trade_id))

        if axp:
            messages.append("- Exit-Price: %s" % t['avg-exit-price'])

        if t['stats']['exit-reason'] != "undefined":
            messages.append("- Cause: %s" % t['stats']['exit-reason'].title())

        return messages

    def process_signal(self, signal):
        message = ""
        locale = "fr"

        #
        # messages
        #

        if signal.signal_type == Signal.SIGNAL_STRATEGY_TRADE_ENTRY:
            messages = self.format_trade_entry(signal.data, locale)
            message = '\n'.join(messages)

        elif signal.signal_type == Signal.SIGNAL_STRATEGY_TRADE_UPDATE:
            messages = self.format_trade_update(signal.data, locale)
            message = '\n'.join(messages)

        elif signal.signal_type == Signal.SIGNAL_STRATEGY_TRADE_EXIT:
            messages = self.format_trade_exit(signal.data, locale)
            message = '\n'.join(messages)

        # if Signal.SIGNAL_STRATEGY_SIGNAL_ENTRY <= signal.signal_type <= Signal.SIGNAL_STRATEGY_TRADE_UPDATE:
        #     if signal.data['way'] not in self._signals_opts:
        #         return
        #
        #     # generic signal reason
        #     action = signal.data['way']
        #
        #     # specified exit reason
        #     if action == "exit" and 'stats' in signal.data and 'exit-reason' in signal.data['stats']:
        #         action = signal.data['stats']['exit-reason']
        #
        #     ldatetime = datetime.fromtimestamp(signal.data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        #
        #     message = "%s@%s (%s) %s %s at %s - #%s in %s" % (
        #         signal.data['symbol'],
        #         signal.data['order-price'],
        #         signal.data['app-name'],
        #         action,
        #         signal.data['direction'],
        #         ldatetime,
        #         signal.data['id'],
        #         signal.data['timeframe'])
        #
        #     if signal.data.get('stop-loss-price') and 'stop-loss' in self._signals_opts:
        #         message += " SL@%s" % (signal.data['stop-loss-price'],)
        #
        #     if signal.data.get('take-profit-price') and 'take-profit' in self._signals_opts:
        #         message += " TP@%s" % (signal.data['take-profit-price'],)
        #
        #     if signal.data.get('profit-loss-pct') is not None:
        #         message += " (%.2f%%)" % (signal.data['profit-loss-pct'],)
        #
        #     if signal.data.get('order-qty') is not None and 'order-qty' in self._signals_opts:
        #         message += " Q:%s" % signal.data['order-qty']
        #
        #     if signal.data.get('label') is not None:
        #         message += " (%s)" % signal.data['label']
        #

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

        elif signal.signal_type == Signal.SIGNAL_STRATEGY_TRADE_ERROR:
            if 'error' not in self._signals_opts:
                return

            border = "orange"

            ldatetime = datetime.fromtimestamp(signal.data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')

            message = "Trade error at %s - #%s on %s" % (
                ldatetime,
                signal.data['trade-id'],
                signal.data['symbol'])

        elif signal.signal_type == Signal.SIGNAL_STRATEGY_SIGNAL_ENTRY:
            # @todo
            return

        elif signal.signal_type == Signal.SIGNAL_STRATEGY_SIGNAL_EXIT:
            # @todo
            return

        elif signal.signal_type == Signal.SIGNAL_MARKET_SIGNAL:
            # @todo
            return

        #
        # store for comparison and queries
        #

        if Signal.SIGNAL_STRATEGY_TRADE_ENTRY <= signal.signal_type <= Signal.SIGNAL_STRATEGY_TRADE_UPDATE:
            # trade local copy
            if signal.data['symbol'] not in self._opened_trades:
                self._opened_trades[signal.data['symbol']] = {}
            opened_trades = self._opened_trades[signal.data['symbol']]

            if signal.data['symbol'] not in self._closed_trades:
                self._closed_trades[signal.data['symbol']] = {}
            closed_trades = self._closed_trades[signal.data['symbol']]

            if signal.data['symbol'] not in self._canceled_trades:
                self._canceled_trades[signal.data['symbol']] = {}
            canceled_trades = self._canceled_trades[signal.data['symbol']]

            if signal.data['way'] == 'entry':
                # opened
                opened_trades[signal.data['id']] = copy.copy(signal.data)

            elif signal.data['way'] == 'update':
                if signal.data['stats']['exit-reason'] in ("canceled-targeted", "canceled-timeout"):
                    # canceled
                    if signal.data['id'] in opened_trades:
                        del opened_trades[signal.data['id']]

                    canceled_trades[signal.data['id']] = copy.copy(signal.data)
                else:
                    # updated
                    opened_trades[signal.data['id']] = copy.copy(signal.data)

            elif signal.data['way'] == 'exit':
                if signal.data['stats']['exit-reason'] in ("canceled-targeted", "canceled-timeout"):
                    # canceled
                    if signal.data['id'] in opened_trades:
                        del opened_trades[signal.data['id']]

                    canceled_trades[signal.data['id']] = copy.copy(signal.data)
                else:
                    # closed
                    if signal.data['id'] in opened_trades:
                        del opened_trades[signal.data['id']]

                    closed_trades[signal.data['id']] = copy.copy(signal.data)

        #
        # send the message
        #

        if message:
            dst = self._webhooks.get('signals')

            if self._avatar_url:
                extra = {
                    'avatar_url': self._avatar_url
                }
            else:
                extra = None

            if dst:
                try:
                    send_to_discord(dst, self._who, '```' + message + '```', extra)
                except:
                    pass

    def receiver(self, signal):
        if not self._playpause or self._backtesting or not signal:
            return

        if signal.source == Signal.SOURCE_STRATEGY:
            if Signal.SIGNAL_STRATEGY_SIGNAL_ENTRY <= signal.signal_type <= Signal.SIGNAL_STRATEGY_ALERT:
                self.push_signal(signal)

        # avoid to public
        # elif signal.source == Signal.SOURCE_WATCHDOG:
        #     if signal.signal_type in (Signal.SIGNAL_WATCHDOG_TIMEOUT, Signal.SIGNAL_WATCHDOG_UNREACHABLE):
        #         self.push_signal(signal)

    #
    # helpers
    #

    def split_and_send(self, dst, msg):
        max_msg_size = 2000 - 6 - 25

        rows = msg.split('\n')
        i = 0

        if self._avatar_url:
            extra = {
                'avatar_url': self._avatar_url
            }
        else:
            extra = None

        while i < len(rows):
            buf = ""

            while (i < len(rows)) and (len(buf) + len(rows[i]) + 1 < max_msg_size):
                buf += rows[i] + '\n'
                i += 1

            if buf:
                send_to_discord(dst, self._who, '```' + buf + '```', extra)

    def format_table(self, data):
        arr = tabulate(data, headers='keys', tablefmt='psql', showindex=False, floatfmt=".2f", disable_numparse=True)
        # remove colors
        arr = arr.replace(Color.ORANGE, '').replace(Color.RED, '').replace(Color.GREEN, '').replace(
            Color.WHITE, '').replace(Color.PURPLE, '')

        return arr

    # def send_tables(self):
    #         if strategy.identifier + '.trades' in self._discord_webhooks:
    #             trades_dst = self._discord_webhooks[strategy.identifier + '.trades']

    #         if strategy.identifier + '.agg-trades' in self._discord_webhooks:
    #             agg_trades_dst = self._discord_webhooks[strategy.identifier + '.agg-trades']

    #         if strategy.identifier + '.closed-trades' in self._discord_webhooks:
    #             closed_trades_dst = self._discord_webhooks[strategy.identifier + '.closed-trades']

    #         if trades_dst:
    #             columns, table, total_size = trades_stats_table(appl, *Terminal.inst().active_content().format(),
    #                   quantities=True, percents=True)
    #             if table:
    #                 arr = self.format_table(table)
    #                 self.split_and_send(trades_dst, arr)
            
    #         if agg_trades_dst:
    #             columns, table, total_size = agg_trades_stats_table(appl, *Terminal.inst().active_content().format(),
    #                   quantities=True)
    #             if table:
    #                 arr = self.format_table(table)
    #                 self.split_and_send(agg_trades_dst, arr)

    #         if closed_trades_dst:
    #             columns, table, total_size = closed_trades_stats_table(appl,
    #                   *Terminal.inst().active_content().format(), quantities=True, percents=True)
    #             if table:
    #                 arr = self.format_table(table)
    #                 self.split_and_send(closed_trades_dst, arr)

    #     return True
