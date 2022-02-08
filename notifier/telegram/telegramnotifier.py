# @date 2022-02-06
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Telegram notification handler

import copy
import time
import traceback
import re
import pytz

from tabulate import tabulate
from datetime import datetime, timedelta

from notifier.notifier import Notifier
from terminal.terminal import Terminal, Color

from notifier.telegram.telegramapi import send_to_telegram, get_telegram_updates
from notifier.notifierexception import NotifierException

from common.signal import Signal

from strategy.helpers.activetradetable import trades_stats_table

import logging

from common.utils import timeframe_to_str, timeframe_from_str

logger = logging.getLogger('siis.notifier.telegram')
error_logger = logging.getLogger('siis.error.notifier.telegram')
traceback_logger = logging.getLogger('siis.traceback.notifier.telegram')


class TelegramNotifier(Notifier):
    """
    Telegram notifier using bot and API.

    @todo getUpdates to receive command from users and check every second news command and reply
    @todo commands
    """

    WAIT_DELAY = 1.0  # 1 second to check bot command

    def __init__(self, identifier, service, options):
        super().__init__("telegram", identifier, service)

        self._backtesting = options.get('backtesting', False)

        notifier_config = service.notifier_config(identifier)

        self._bot_token = notifier_config.get('bot-token', '')
        self._chats = notifier_config.get('chats', {})
        self._commands = notifier_config.get('commands', {})
        self._op_commands = notifier_config.get('op-commands', {})

        self._display_percent = False
        self._active_trades = notifier_config.get('active-trades', False)
        self._historical_trades = notifier_config.get('historical-trades', False)

        self._last_update_id = 0
        self._last_command_update = 0.0

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

        has_signal = False

        if self._chats.get('signals'):
            # only if signals chat is defined

            # could validate chat-id format
            for k, chat_id in self._chats.items():
                try:
                    int(chat_id)
                except ValueError:
                    raise NotifierException(self.name, self.identifier, "Malformed chat-id %s for chat %s" % (
                        chat_id, k))

            logger.info("Notifier %s - %s : signals chat-id found and valid, start it..." % (
                self.name, self.identifier))

            has_signal = True
        else:
            logger.warning("Notifier %s - %s : signals chat-id not found, not started !" % (
                self.name, self.identifier))
            return False

        if self._commands:
            # could validate chat-id and from-id format
            for k, chat_id in self._commands.items():
                if k not in ('trade', 'long', 'short', 'close', 'stop-loss', 'take-profit'):
                    raise NotifierException(self.name, self.identifier, "Unsupported command %s" % k)

                try:
                    int(chat_id)
                except ValueError:
                    raise NotifierException(self.name, self.identifier, "Malformed chat-id %s for command %s" % (
                        chat_id, k))

        # @todo op-commands

        if has_signal:
            return super().start(options)
        else:
            logger.warning("Notifier %s - %s : signals chat-id not found, not started !" % (
                self.name, self.identifier))
            return False

    def terminate(self):
        pass

    def wait_signal(self):
        self._condition.acquire()
        while self._running and not self._signals:
            if self._commands:
                # have commands to process, wake-up frequently
                self._condition.wait(TelegramNotifier.WAIT_DELAY)
                break
            else:
                self._condition.wait()
        self._condition.release()

    def update(self):
        if super().update():
            now = time.time()

            if now - self._last_command_update >= TelegramNotifier.WAIT_DELAY:
                try:
                    self.retrieve_and_process_commands()
                except:
                    pass

                self._last_command_update = now

            return True

        return False

    def notify(self):
        pass

    def process_signal(self, signal):
        message = ""
        locale = "fr"

        if Signal.SIGNAL_STRATEGY_SIGNAL_ENTRY <= signal.signal_type <= Signal.SIGNAL_STRATEGY_TRADE_UPDATE:
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
                if signal.data['exit-reason'] in ("canceled-targeted", "canceled-timeout"):
                    # canceled
                    if signal.data['id'] in opened_trades:
                        del opened_trades[signal.data['id']]

                    canceled_trades[signal.data['id']] = copy.copy(signal.data)
                else:
                    # updated
                    opened_trades[signal.data['id']] = copy.copy(signal.data)

            elif signal.data['way'] == 'exit':
                if signal.data['exit-reason'] in ("canceled-targeted", "canceled-timeout"):
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
        # messages
        #

        if signal.signal_type == Signal.SIGNAL_STRATEGY_SIGNAL_ENTRY:
            t = signal.data

            trade_id = t['id']
            symbol = t['symbol']

            messages = []

            open_dt = TelegramNotifier.parse_utc_datetime(t['entry-open-time'])

            op = float(t.get('order-price', "0"))
            aep = float(t.get('avg-entry-price', "0"))

            if 'entry-order-type' in t['stats']:
                order_type = t['stats']['entry-order-type']
            elif aep:
                order_type = "market"
            elif op:
                order_type = "limit"
            else:
                order_type = "undefined"

            messages.append("%s %s:%s [ NEW ]" % (t['direction'].capitalize(), symbol, trade_id))
            messages.append("- %s: %s" % (order_type, TelegramNotifier.format_datetime(open_dt, locale)))

            if aep:
                messages.append("- Entry-Price: %s" % t['avg-entry-price'])
            elif op:
                messages.append("- Order-Price: %s" % t['order-price'])

            if t['timeframe']:
                messages.append("- Timeframe %s" % t['timeframe'])

            if t['label']:
                messages.append("- Context %s" % t['label'])

            if t['entry-timeout'] and not aep:
                # before in position
                et_tf = timeframe_from_str(t['entry-timeout'])
                if et_tf > 0.0:
                    entry_timeout_dt = open_dt + timedelta(seconds=et_tf)
                    messages.append("- Cancel entry after : %s" % TelegramNotifier.format_datetime(entry_timeout_dt))

            if t['expiry'] and aep:
                # until in position
                expiry_dt = open_dt + timedelta(seconds=t['expiry'])
                messages.append("- Close expiry after : %s" % TelegramNotifier.format_datetime(expiry_dt))

            if float(t['take-profit-price']):
                messages.append("- Take-Profit: %s" % t['take-profit-price'])
            if float(t['stop-loss-price']):
                messages.append("- Stop-Loss: %s" % t['stop-loss-price'])

            message = '\n'.join(messages)

        elif signal.signal_type == Signal.SIGNAL_STRATEGY_TRADE_UPDATE:
            t = signal.data

            trade_id = t['id']
            symbol = t['symbol']

            messages = []

            messages.append("%s %s:%s [ UPDATE ]" % (t['direction'].capitalize(), symbol, trade_id))

            if t['timeframe']:
                messages.append("- Timeframe %s" % t['timeframe'])

            if float(t['take-profit-price']):
                messages.append("- Take-Profit: %s" % t['take-profit-price'])
            if float(t['stop-loss-price']):
                messages.append("- Stop-Loss: %s" % t['stop-loss-price'])

            message = '\n'.join(messages)

        elif signal.signal_type == Signal.SIGNAL_STRATEGY_TRADE_EXIT:
            t = signal.data

            trade_id = t['id']
            symbol = t['symbol']

            messages = []

            axp = float(t.get('avg-exit-price', "0"))

            messages.append("%s %s:%s [ CLOSE ]" % (t['direction'].capitalize(), symbol, trade_id))

            if axp:
                messages.append("- Exit-Price: %s" % t['avg-exit-price'])

            if signal.data['exit-reason'] != "undefined":
                messages.append("- Cause: %s" % t['exit-reason'].title())

            message = '\n'.join(messages)

        elif signal.signal_type == Signal.SIGNAL_STRATEGY_TRADE_ERROR:
            if 'error' not in self._signals_opts:
                return

            border = "orange"

            ldatetime = datetime.fromtimestamp(signal.data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')

            message = "Trade error at %s - #%s on %s" % (
                ldatetime,
                signal.data['trade-id'],
                signal.data['symbol'])

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

        elif signal.signal_type == Signal.SIGNAL_MARKET_SIGNAL:
            return

        if message:
            dst = self._chats.get('signals')
            if dst:
                try:
                    send_to_telegram(self._bot_token, dst, message)
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

    def retrieve_and_process_commands(self):
        initial = self._last_update_id == 0

        try:
            self._last_update_id, commands = get_telegram_updates(self._bot_token, self._last_update_id)
        except:
            return

        if initial:
            # do not process initials
            return

        for chat_id, command in commands:
            parts = command.split(' ')
            if not parts:
                # not a command
                continue

            cmd = parts[0].lstrip('/')
            if cmd not in self._commands:
                # ignored command
                continue

            if str(chat_id) != self._commands[cmd]:
                # ignored command invalid source
                continue

            # @todo could compare user command to avoid redo the same command...
            if cmd == "trade":
                try:
                    self.process_trade_command(parts[1:], chat_id)
                except Exception as e:
                    error_logger.error(repr(e))
                    traceback_logger.error(traceback.format_exc())

    def process_trade_command(self, command, chat_id, locale="fr"):
        messages = []

        if len(command) == 1:
            symbol = command[0]
            trade_id = 0
        elif len(command) == 2:
            symbol = command[0]
            try:
                trade_id = int(command[1])
            except ValueError:
                # invalid parameter
                return False
        else:
            # invalid parameters
            return False

        if not symbol:
            # invalid parameters
            return False

        if symbol not in self._strategy_service.strategy.symbols_ids():
            # not managed symbol
            return True

        opened_trades = self._opened_trades.get(symbol, {})
        canceled_trades = self._canceled_trades.get(symbol, {})
        closed_trades = self._closed_trades.get(symbol, {})

        if not trade_id:
            # retrieve the list of trades
            if opened_trades:
                messages.append("There is %s opened trades for %s :" % (len(opened_trades), symbol))
                messages.append(', '.join([str(t['id']) for k, t in opened_trades.items()]))
            else:
                messages.append("There is no opened trades for %s" % symbol)

            if canceled_trades:
                messages.append("There is %s canceled trades for %s :" % (len(canceled_trades), symbol))
                messages.append(', '.join([str(t['id']) for k, t in canceled_trades.items()]))
            else:
                messages.append("There is no canceled trades for %s" % symbol)

            if closed_trades:
                messages.append("There is %s closed trades for %s :" % (len(closed_trades), symbol))
                messages.append(', '.join([str(t['id']) for k, t in closed_trades.items()]))
            else:
                messages.append("There is no closed trades for %s" % symbol)

        else:
            # retrieve the specified trade
            if trade_id in opened_trades:
                t = opened_trades[trade_id]

                if 'first-realized-entry-datetime' in t['stats']:
                    open_dt = TelegramNotifier.parse_utc_datetime(t['stats']['first-realized-entry-datetime'])
                else:
                    open_dt = TelegramNotifier.parse_utc_datetime(t['entry-open-time'])

                aep = float(t.get('avg-entry-price', "0"))
                axp = float(t.get('avg-exit-price', "0"))
                op = float(t.get('order-price', "0"))

                if axp:
                    messages.append("%s %s:%s [ CLOSING ]" % (t['direction'].capitalize(), symbol, trade_id))
                    messages.append("- Opened: %s" % TelegramNotifier.format_datetime(open_dt, locale))
                elif aep:
                    messages.append("%s %s:%s [ ACTIVE ]" % (t['direction'].capitalize(), symbol, trade_id))
                    messages.append("- Opened: %s" % TelegramNotifier.format_datetime(open_dt, locale))
                else:
                    messages.append("%s %s:%s [ PENDING ]" % (t['direction'].capitalize(), symbol, trade_id))
                    messages.append("- Signaled: %s" % TelegramNotifier.format_datetime(open_dt, locale))

                if t['timeframe']:
                    messages.append("- Timeframe %s" % t['timeframe'])

                if t['label']:
                    messages.append("- Context %s" % t['label'])

                if t['entry-timeout'] and not aep:
                    # before in position
                    et_tf = timeframe_from_str(t['entry-timeout'])
                    if et_tf > 0.0:
                        entry_timeout_dt = open_dt + timedelta(seconds=et_tf)
                        messages.append("- Cancel entry after : %s" % TelegramNotifier.format_datetime(entry_timeout_dt))

                if t['expiry'] and aep:
                    # until in position
                    expiry_dt = open_dt + timedelta(seconds=t['expiry'])
                    messages.append("- Close expiry after : %s" % TelegramNotifier.format_datetime(expiry_dt))

                if aep:
                    messages.append("- Entry-Price: %s" % t['avg-entry-price'])
                elif op:
                    messages.append("- Order-Price: %s" % t['order-price'])

                if float(t['take-profit-price']):
                    messages.append("- Take-Profit: %s" % t['take-profit-price'])
                if float(t['stop-loss-price']):
                    messages.append("- Stop-Loss: %s" % t['stop-loss-price'])

                if aep:
                    instrument = self.service.strategy_service.strategy().instrument(symbol)

                    upnl = TelegramNotifier.estimate_profit_loss(instrument, t)
                    messages.append("- Unrealized-PNL %.2f%%" % (upnl * 100.0,))

            elif trade_id in canceled_trades:
                t = canceled_trades[trade_id]
                messages.append("Trade %s for %s was canceled before entering" % (trade_id, symbol))

            elif trade_id in closed_trades:
                t = closed_trades[trade_id]

                if 'last-realized-exit-datetime' in t['stats']:
                    close_dt = TelegramNotifier.parse_utc_datetime(t['stats']['last-realized-exit-datetime'])
                else:
                    close_dt = TelegramNotifier.parse_utc_datetime(t['exit-open-time'])

                aep = float(t['avg-entry-price'])
                axp = float(t['avg-exit-price'])
                op = float(t['order-price'])

                messages.append("%s %s:%s. Closed: %s [ CLOSED ]" % (
                    t['direction'].capitalize(), symbol, trade_id, TelegramNotifier.format_datetime(
                        close_dt, locale)))

                if t['timeframe']:
                    messages.append("- Timeframe %s" % t['timeframe'])

                if t['label']:
                    messages.append("- Context %s" % t['label'])

                if aep:
                    messages.append("- Entry-Price: %s" % t['avg-entry-price'])
                elif op:
                    messages.append("- Order-Price: %s" % t['order-price'])

                if axp:
                    messages.append("- Exit-Price: %s" % t['avg-exit-price'])

                if float(t['take-profit-price']):
                    messages.append("- Take-Profit: %s" % t['take-profit-price'])
                if float(t['stop-loss-price']):
                    messages.append("- Stop-Loss: %s" % t['stop-loss-price'])

                if t['profit-loss-pct']:
                    messages.append("- Realized PNL: %.2f%% (including common fees)" % t['profit-loss-pct'])

            else:
                messages.append("Trade %s:%s does not exists" % (symbol, trade_id))

        if messages and chat_id:
            try:
                send_to_telegram(self._bot_token, chat_id, '\n'.join(messages))
            except:
                pass

        return True

    @staticmethod
    def format_datetime(dt, local="fr"):
        if local == "fr":
            dt = dt.replace(tzinfo=pytz.timezone('Europe/Paris'))
            return dt.strftime('%Y-%m-%d %H:%M:%S (Paris)') if dt else ''
        else:
            return dt.strftime('%Y-%m-%d %H:%M:%S (UTC)') if dt else ''

    @staticmethod
    def estimate_profit_loss(instrument, trade):
        """
        Estimate PLN without fees.
        """
        direction = 1 if trade['direction'] == "long" else -1

        # estimation at close price
        close_exec_price = instrument.close_exec_price(direction)

        # no current price update
        if not close_exec_price:
            return 0.0

        entry_price = float(trade['avg-entry-price'])

        if direction > 0 and entry_price > 0:
            profit_loss = (close_exec_price - entry_price) / entry_price
        elif direction < 0 and entry_price > 0:
            profit_loss = (entry_price - close_exec_price) / entry_price
        else:
            profit_loss = 0.0

        return profit_loss

    @staticmethod
    def parse_utc_datetime(utc_dt):
        if utc_dt:
            return datetime.strptime(utc_dt, '%Y-%m-%dT%H:%M:%S.%fZ')
        else:
            return datetime.now()
