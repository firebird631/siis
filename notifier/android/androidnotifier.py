# @date 2018-11-30
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Android notifier bot message post.

import time
import logging
import traceback

from importlib import import_module
from datetime import datetime, timedelta

from notifier.notifier import Notifier

from config import utils

from trader.position import Position
from notifier.android.androidpush import send_to_android

from common.signal import Signal

from common.utils import timeframe_to_str

import logging
logger = logging.getLogger('siis.notifier.android')
error_logger = logging.getLogger('siis.error.notifier.android')


class AndroidNotifier(Notifier):
    """
    Android Firebase push notifier.
    """

    def __init__(self, name, identifier, service, options):
        super().__init__("android", identifier, service)

        self._backtesting = options.get('backtesting', False)

        notifier_config = service.notifier_config(name)

        self._display_percent = False

        self._who = notifier_config.get('who', 'SiiS')
        self._auth_key = notifier_config.get('auth-key')
        self._channels = notifier_config.get('channels', {
            "signals": "/topics/default",  # @todo
            "watchdog": "/topics/default"  # @todo
        })

        if 'signals' not in self._channels:
            self._channels['signals'] = "/topics/default"  # @todo

        if 'watchdog' not in self._channels:
            self._channels['watchdog'] = "/topics/default"  # @todo

        self._signals_opts = notifier_config.get('signals', ("entry", "exit" "take-profit", "stop-loss", "quantity"))
        self._watchdog = notifier_config.get('watchdog', ("timeout", "unreachable"))
        self._account = notifier_config.get('account', ("balance", "assets-balance"))

    def start(self, options):
        if self._auth_key and self._channels.get('signals') and not self._backtesting:
            return super().start(options)
        else:
            return False

    def terminate(self):
        pass

    def notify(self):
        pass

    def process_signal(self, signal):
        label = ""
        message = ""
        sound = "default"
        channel = ""

        if signal.signal_type in (Signal.SIGNAL_STRATEGY_SIGNAL, Signal.SIGNAL_STRATEGY_ENTRY, Signal.SIGNAL_STRATEGY_EXIT):
            if not signal.data['action'] in self._signals_opts:
                return

            channel = self._channels.get('signals')

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

            if signal.data['stop-loss'] and 'stop-loss' in self._signals_opts:
                message += " SL@%s" % (signal.data['stop-loss'],)

            if signal.data['take-profit'] and 'take-profit' in self._signals_opts:
                message += " TP@%s" % (signal.data['take-profit'],)

            if signal.data['profit-loss'] is not None:
                message += " (%.2f%%)" % ((signal.data['profit-loss'] * 100),)

            if signal.data['quantity'] is not None and 'quantity' in self._signals_opts:
                message += " Q:%s" % signal.data['quantity']

            if signal.data['comment'] is not None:
                message += " (%s)" % signal.data['comment']

        elif signal.signal_type == Signal.SIGNAL_STRATEGY_SIGNAL:
            return

        elif signal.signal_type == Signal.SIGNAL_MARKET_SIGNAL:
            return

        elif signal.signal_type == Signal.SIGNAL_WATCHDOG_TIMEOUT:
            if not 'timeout' in self._watchdog:
                return

            channel = self._channels.get('watchdog')

            ldatetime = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
            label = "Watchdog timeout pid %i service" % (signal.data[0], signal.data[1])

            message = "Watchdog timeout pid %i service %s after %.0f' at %s" % (
                signal.data[0], signal.data[1], signal.data[2], ldatetime)

        elif signal.signal_type == Signal.SIGNAL_WATCHDOG_UNREACHABLE:
            if not 'unreachable' in self._watchdog:
                return

            channel = self._channels.get('watchdog')

            ldatetime = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
            label = "Watchdog unreachable service %s'" % signal.data[0]
            message = "Watchdog unreachable service %s at %s - %s" % (signal.data[0], ldatetime, signal.data[1])

        if message:
            if channel and self._auth_key:
                try:
                    send_to_android(self._auth_key, channel, self._who, message, sound)
                except:
                    pass

    def command(self, command_type, data):
        pass

    def receiver(self, signal):
        if not self._playpause or self._backtesting or not signal:
            return

        if signal.source == Signal.SOURCE_STRATEGY:
            if signal.signal_type in (Signal.SIGNAL_STRATEGY_SIGNAL, Signal.SIGNAL_STRATEGY_ENTRY, Signal.SIGNAL_STRATEGY_EXIT):

                self.push_signal(signal)

        elif signal.source == Signal.SOURCE_WATCHDOG:
            if signal.signal_type in (Signal.SIGNAL_WATCHDOG_TIMEOUT, Signal.SIGNAL_WATCHDOG_UNREACHABLE):
                self.push_signal(signal)
