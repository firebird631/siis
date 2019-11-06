# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Desktop notification handler

import collections
import threading
import os
import time
import logging
import subprocess
import traceback

from importlib import import_module
from datetime import datetime, timedelta

from notifier.notifier import Notifier

from config import utils

from trader.position import Position
from notifier.discord.webhooks import send_to_discord

from common.baseservice import BaseService
from common.signal import Signal

from terminal.terminal import Terminal

from common.utils import timeframe_to_str

import logging
logger = logging.getLogger('siis.notifier.desktop')
error_logger = logging.getLogger('siis.error.notifier.desktop')
signal_logger = logging.getLogger('siis.signal')


class DesktopNotifier(Notifier):
    """
    Desktop notifier for desktop popup and audio alerts.
    @todo Terminal.inst().notice(message, view="signal") should goes to the SignalView
    """

    AUDIO_ALERT_SIMPLE = 0
    AUDIO_ALERT_INTENSIVE = 1
    AUDIO_ALERT_WARNING = 2
    AUDIO_ALERT_HAPPY = 3

    DEFAULT_AUDIO_DEVICE = "pulse"

    DEFAULT_AUDIO = [
        ('/usr/share/sounds/info.wav', 3),
        ('/usr/share/sounds/phone.wav', 2),
        ('/usr/share/sounds/error.wav', 5),
        ('/usr/share/sounds/logout.wav', 1)
    ]

    def __init__(self, name, identifier, service, options):
        super().__init__("desktop", identifier, service)

        self._backtesting = options.get('backtesting', False)

        notifier_config = service.notifier_config(name)

        # default audio alert and popups stats configurable
        self._audible = notifier_config.get('play-alerts', False)
        self._popups = notifier_config.get('display-popups', False)

        # @todo map audio alerts audio_config.gett('alerts')
        audio_config = notifier_config.get('audio', {})

        self._audio_device = audio_config.get('device', DesktopNotifier.DEFAULT_AUDIO_DEVICE)

        # @todo parse and map audio alerts
        self._alerts = DesktopNotifier.DEFAULT_AUDIO

    def start(self, options):
        self.notify2 = None

        try:
            self.notify2 = import_module('notify2', package='')
        except ModuleNotFoundError as e:
            logger.error(repr(e))

        # lib notify
        if self.notify2:
            self.notify2.init('SiiS')

        return super().start(options)

    def terminate(self):
        if self.notify2:
            self.notify2.uninit()
            self.notify2 = None

    def notify(self):
        pass

    def process_signal(self, signal):
        label = ""
        message = ""
        icon = "contact-new"
        now = time.time()
        audio_alert = None

        if signal.signal_type == Signal.SIGNAL_SOCIAL_ENTER:
            # here we only assume that because of what 1broker return to us but should be timestamp in the model
            entry_date = signal.data.entry_date + timedelta(hours=2)
            position_timestamp = time.mktime(entry_date.timetuple())
            audio_alert = DesktopNotifier.AUDIO_ALERT_SIMPLE

            if now - position_timestamp > 120 * 60:
                return

            label = "Entry position on %s" % (signal.data.symbol,)
            message = "Trader %s enter %s on %s at %s (x%s)" % (
                signal.data.author.name if signal.data.author is not None else "???",
                "long" if signal.data.direction == Position.LONG else "short",
                signal.data.symbol,
                signal.data.entry_price,
                signal.data.leverage)

        elif signal.signal_type == Signal.SIGNAL_SOCIAL_EXIT:
            # here we only assume that because of what 1broker return to us but should be timestamp in the model
            exit_date = signal.data.exit_date + timedelta(hours=2)
            position_timestamp = time.mktime(exit_date.timetuple())
            audio_alert = DesktopNotifier.AUDIO_ALERT_SIMPLE

            if now - position_timestamp > 120 * 60:
                return

            label = "Exit position on %s" % (signal.data.symbol,)
            message = "Trader %s exit %s on %s at %s" % (
                signal.data.author.name,
                "long" if signal.data.direction == Position.LONG else "short",
                signal.data.symbol,
                signal.data.exit_price)

        # # @todo a threshold... or a timelimit
        # elif signal.signal_type == Signal.SIGNAL_TRADE_ALERT:
        #     icon = "go-down"
        #     label = "Position loss on %s" % (signal.data.symbol,)
        #     audio_alert = DesktopNotifier.AUDIO_ALERT_WARNING

        #     message = "Position %s %s of %s on %s start at %s %s is in regretable loss %s (%s%%) :$" % (
        #         signal.data.position_id,
        #         "long" if signal.data.direction == Position.LONG else "short",
        #         signal.data.author.name if signal.data.author is not None else "???",
        #         signal.data.trader.name,
        #         signal.data.entry_price,
        #         signal.data.symbol,
        #         signal.data.profit_loss,
        #         signal.data.profit_loss_rate * 100.0)

        # elif signal.signal_type == Signal.SIGNAL_TRADE_ENJOY:
        #     icon = "go-up"
        #     label = "Position profit on %s" % (signal.data.symbol,)
        #     audio_alert = DesktopNotifier.AUDIO_ALERT_SIMPLE

        #     message = "Position %s %s of %s on %s start at %s %s is in enjoyable profit %s (%s%%) :)" % (
        #         signal.data.position_id,
        #         "long" if signal.data.direction == Position.LONG else "short",
        #         signal.data.author.name if signal.data.author is not None else "???",
        #         signal.data.trader.name,
        #         signal.data.entry_price,
        #         signal.data.symbol,
        #         signal.data.profit_loss,
        #         signal.data.profit_loss_rate * 100.0)

        elif signal.signal_type == Signal.SIGNAL_STRATEGY_ENTRY_EXIT:
            # @todo in addition of entry/exit, modification and a reason of the exit/modification
            icon = "contact-new"
            direction = "long" if signal.data['direction'] == Position.LONG else "short"
            audio_alert = DesktopNotifier.AUDIO_ALERT_SIMPLE

            if signal.data['action'] == 'stop':
                audio_alert = DesktopNotifier.AUDIO_ALERT_WARNING

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

            # log them to the signal view (@todo might goes to the View)
            Terminal.inst().notice(message, view="signal")

            # and in signal logger (@todo to be moved to a SignalView)
            signal_logger.info(message)

        # process sound
        if not self._backtesting and self._audible and audio_alert is not None:
            self.play_audio_alert(audio_alert)

        if not self._backtesting and self._popups and message:
            if self.notify2:
                n = self.notify2.Notification(label, message, icon)
                n.show()

        elif signal.signal_type == Signal.SIGNAL_STRATEGY_SIGNAL:
            return

        elif signal.signal_type == Signal.SIGNAL_MARKET_SIGNAL:
            return

        elif signal.signal_type == Signal.SIGNAL_WATCHDOG_TIMEOUT:
            return

        elif signal.signal_type == Signal.SIGNAL_WATCHDOG_UNREACHABLE:
            return

    def command(self, command_type, data):
        if command_type == "toggle-popup":
            self._popups = not self._popups
            Terminal.inst().action("Desktop notification are now %s" % ("actives" if self._popups else "disabled",), view='status')
        elif command_type == "toggle-audible":
            self._audible = not self._audible
            Terminal.inst().action("Desktop audio alertes are now %s" % ("actives" if self._audible else "disabled",), view='status')

    def receiver(self, signal):
        if not self._playpause or not signal:  # or self._backtesting :
            return

        if signal.source == Signal.SOURCE_STRATEGY:
            if signal.signal_type in (Signal.SIGNAL_SOCIAL_ENTER, Signal.SIGNAL_SOCIAL_EXIT, Signal.SIGNAL_STRATEGY_ENTRY_EXIT):
                self.push_signal(signal)

        elif signal.source == Signal.SOURCE_WATCHDOG:
            self.push_signal(signal)

    #
    # helpers
    #

    def play_audio_alert(self, audio_alert):
        # @todo using new conf
        if not self._backtesting and self._audible and audio_alert is not None and 0 <= audio_alert <= len(self._alerts):
            try:
                for i in range(0, self._alerts[audio_alert][1]):
                    subprocess.Popen(['aplay', '-D', self._audio_device, self._alerts[audio_alert][0]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except:
                pass

    def play_wave(self, freq, duration, mode="sine"):
        if not self.backtesting and self._audible and freq and duration and mode:
            try:
                os.system('play --no-show-progress --null --channels 1 synth %s %s %f' % (duration, mode, freq))
            except:
                pass
