# @date 2022-02-06
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Telegram notification handler

import copy
import time
import traceback

from datetime import datetime, timedelta

from notifier.notifier import Notifier

from notifier.telegram.telegramapi import send_to_telegram, get_telegram_updates
from notifier.notifierexception import NotifierException

from common.signal import Signal

import logging

from common.utils import timeframe_from_str

logger = logging.getLogger('siis.notifier.telegram')
error_logger = logging.getLogger('siis.error.notifier.telegram')
traceback_logger = logging.getLogger('siis.traceback.notifier.telegram')


class TelegramNotifier(Notifier):
    """
    Telegram notifier using bot and API.

    @todo trading commands
    """

    WAIT_DELAY = 1.0  # 1 second to check bot command

    def __init__(self, identifier: str, service, options: dict):
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

        self._opened_trades = {}
        self._closed_trades = {}
        self._canceled_trades = {}

    def start(self, options: dict):
        if self._backtesting:
            logger.warning("Notifier %s - %s : signals not started because of backtesting !" % (
                self.name, self.identifier))
            return False

        if self._chats.get('signals'):
            # only if signals chat is defined

            # could validate chat-id format
            for k, chat_id in self._chats.items():
                try:
                    int(chat_id)
                except ValueError:
                    raise NotifierException(self.name, self.identifier, "Malformed chat-id %s for chat %s" % (
                        chat_id, k))

            has_signal = True

            logger.info("Notifier %s - %s : signals chat-id found and valid, start it..." % (
                self.name, self.identifier))
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

        # template
        if self._template not in ("default", "light", "verbose"):
            raise NotifierException(self.name, self.identifier, "Invalid template name %s" % self._template)

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

            if self._commands and now - self._last_command_update >= TelegramNotifier.WAIT_DELAY:
                try:
                    self.retrieve_and_process_commands()
                except:
                    pass

                self._last_command_update = now

            return True

        return False

    def notify(self):
        pass

    def format_trade_entry(self, t, locale):
        messages = []

        trade_id = t['id']
        symbol = t['symbol']
        alias = t['alias']

        open_dt = Notifier.parse_utc_datetime(t['entry-open-time'])

        op = float(t.get('order-price', "0"))
        aep = float(t.get('avg-entry-price', "0"))

        order_type = t['stats']['entry-order-type']

        if self._template in ("default", "verbose"):
            messages.append("%s %s:%s [ NEW ]" % (t['direction'].capitalize(), alias or symbol, trade_id))
            messages.append("- %s: %s" % (order_type.title(), TelegramNotifier.format_datetime(open_dt, locale)))

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
                    messages.append("- Cancel entry after : %s" % TelegramNotifier.format_datetime(entry_timeout_dt))

            if t['expiry'] and aep:
                # until in position
                expiry_dt = open_dt + timedelta(seconds=t['expiry'])
                messages.append("- Close expiry after : %s" % TelegramNotifier.format_datetime(expiry_dt))

        elif self._template == "light":
            messages.append("%s %s:%s [ NEW ]" % (t['direction'].capitalize(), alias or symbol, trade_id))

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
        alias = t['alias']

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
                messages.insert(0, "%s %s:%s [ UPDATE ]" % (t['direction'].capitalize(), alias or symbol, trade_id))

        return messages

    def format_trade_exit(self, t, locale):
        messages = []

        trade_id = t['id']
        symbol = t['symbol']
        alias = t['alias']

        axp = float(t.get('avg-exit-price', "0"))

        messages.append("%s %s:%s [ CLOSE ]" % (t['direction'].capitalize(), alias or symbol, trade_id))

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

        if symbol not in self.service.strategy_service.strategy().symbols_ids():
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
                    messages.append("- Timeframe: %s" % t['timeframe'])

                if t['label']:
                    messages.append("- Context: %s" % t['label'])

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

                    upnl = Notifier.estimate_profit_loss(instrument, t)
                    messages.append("- Unrealized-PNL %.2f%%" % (upnl * 100.0,))

            elif trade_id in canceled_trades:
                t = canceled_trades[trade_id]
                messages.append("Trade %s for %s was canceled before entering" % (trade_id, symbol))

            elif trade_id in closed_trades:
                t = closed_trades[trade_id]

                if 'last-realized-exit-datetime' in t['stats']:
                    close_dt = Notifier.parse_utc_datetime(t['stats']['last-realized-exit-datetime'])
                else:
                    close_dt = Notifier.parse_utc_datetime(t['exit-open-time'])

                aep = float(t['avg-entry-price'])
                axp = float(t['avg-exit-price'])
                op = float(t['order-price'])

                messages.append("%s %s:%s. Closed: %s [ CLOSED ]" % (
                    t['direction'].capitalize(), symbol, trade_id, Notifier.format_datetime(
                        close_dt, locale)))

                if t['timeframe']:
                    messages.append("- Timeframe: %s" % t['timeframe'])

                if t['label']:
                    messages.append("- Context: %s" % t['label'])

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
