# @date 2022-02-06
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Telegram notification handler

import time
import traceback
import re

from tabulate import tabulate
from datetime import datetime, timedelta

from notifier.notifier import Notifier
from terminal.terminal import Terminal, Color

from notifier.telegram.telegramapi import send_to_telegram, get_telegram_updates
from notifier.notifierexception import NotifierException

from common.signal import Signal

from strategy.helpers.activetradetable import trades_stats_table

import logging

from common.utils import timeframe_to_str

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

        # @todo update message formatting
        if Signal.SIGNAL_STRATEGY_SIGNAL_ENTRY <= signal.signal_type <= Signal.SIGNAL_STRATEGY_TRADE_UPDATE:
            if signal.data['way'] not in self._signals_opts:
                return

            # generic signal reason
            action = signal.data['way']

            # specified exit reason
            if action == "exit" and 'stats' in signal.data and 'exit-reason' in signal.data['stats']:
                action = signal.data['stats']['exit-reason']

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

            logger.info("trade command %s : %s" % (chat_id, parts))

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

    def process_trade_command(self, command, chat_id):
        message = None

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

        strategy = self.service.strategy_service.strategy()
        strategy_trader = None

        if symbol:
            instrument = strategy.find_instrument(symbol)
            market_id = instrument.market_id if instrument else None

            strategy_trader = strategy._strategy_traders.get(market_id)

        if not strategy_trader:
            message = "The market %s is not supported" % symbol

        # retrieve the list of trades
        elif not trade_id:
            trade_list = strategy_trader.list_trades()
            if trade_list:
                message = "There is %s trades for %s : \n%s" % (
                    symbol, len(trade_list), ', '.join([str(tid) for tid in trade_list]))
            else:
                message = "There is not trades for %s" % symbol

        # retrieve the specified trade
        else:
            with strategy_trader._trade_mutex:
                found_trade = None

                for trade in strategy_trader.trades:
                    if trade.id == trade_id:
                        found_trade = trade
                        break

                if found_trade:
                    if found_trade.first_realized_entry_time:
                        open_dt = datetime.fromtimestamp(found_trade.first_realized_entry_time).strftime(
                            '%Y-%m-%d %H:%M:%S')
                    elif found_trade.eot:
                        open_dt = datetime.fromtimestamp(found_trade.eot).strftime('%Y-%m-%d %Hh%M:%S')
                    else:
                        open_dt = '???'

                    if found_trade.axp:
                        message = "Trade %s:%s. Opened: %s [ CLOSING ]" % (
                            symbol, trade_id, open_dt)
                    elif found_trade.aep:
                        message = "Trade %s:%s. Opened: %s [ ACTIVE ]" % (
                            symbol, trade_id, open_dt)
                    else:
                        message = "Trade %s:%s. Signaled: %s [ WAITING ]" % (
                            symbol, trade_id, open_dt)

                    if found_trade.timeframe:
                        message += "\n- Timeframe %s" % found_trade.timeframe_to_str()

                    if found_trade.entry_timeout and found_trade.eot:
                        entry_timeout = found_trade.eot + timedelta(seconds=found_trade.entry_timeout)
                        message += "\n- Cancel entry after : %s" % entry_timeout.strftime('%Y-%m-%d %H:%M:%S')

                    if found_trade.expiry and found_trade.first_realized_entry_time:
                        expiry = found_trade.eot + timedelta(seconds=found_trade.entry_timeout)
                        message += "\n- Close expiry after : %s" % expiry.strftime('%Y-%m-%d %H:%M:%S')

                    if found_trade.aep:
                        message += "\n- Entry-Price: %s" % strategy_trader.instrument.format_price(trade.aep)
                    elif found_trade.op:
                        message += "\n- Entry-Price: %s" % strategy_trader.instrument.format_price(trade.op)

                    if found_trade.take_profit:
                        message += "\n- Take-Profit: %s" % strategy_trader.instrument.format_price(trade.take_profit)
                    if found_trade.stop_loss:
                        message += "\n- Stop-Loss: %s" % strategy_trader.instrument.format_price(trade.stop_loss)

                    if found_trade.aep:
                        upnl = found_trade.estimate_profit_loss(strategy_trader.instrument)
                        if upnl:
                            message += "\n- Unrealized-PNL %.2f%%" % (upnl * 100.0,)
                else:
                    message = "There is no trade for %s with identifier %s" % (symbol, trade_id)

            # lookup for trade history
            # @todo

        if message and chat_id:
            try:
                send_to_telegram(self._bot_token, chat_id, message)
            except:
                pass

        return True
