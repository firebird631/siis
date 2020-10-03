# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Desktop notification handler

import collections
import threading
import os
import copy
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

import logging
logger = logging.getLogger('siis.notifier.desktop')
error_logger = logging.getLogger('siis.error.notifier.desktop')
signal_logger = logging.getLogger('siis.signal.desktop')


class DesktopNotifier(Notifier):
    """
    Desktop notifier for desktop popup and audio alerts.

    @todo Strategey alert notifications
    """

    AUDIO_ALERT_DEFAULT = 0
    AUDIO_ALERT_NOTIFY = 1
    AUDIO_ALERT_WARNING = 2
    AUDIO_ALERT_CRITICAL = 3
    AUDIO_ALERT_NETWORK_ONLINE = 4
    AUDIO_ALERT_NETWORK_OFFLINE = 5
    AUDIO_ALERT_SIGNAL_NEW = 6
    AUDIO_ALERT_TRADE_WIN = 7
    AUDIO_ALERT_TRADE_LOST = 8
    AUDIO_ALERT_UP = 9
    AUDIO_ALERT_DOWN = 10

    DEFAULT_AUDIO_DEVICE = "pulse"

    # default alerts profiles
    DEFAULT_ALERTS = [
        ('/usr/share/sounds/info.wav', 2, 'contact-new'),
        ('/usr/share/sounds/phone.wav', 2, 'contact-new'),
        ('/usr/share/sounds/error.wav', 5, 'dialog-error'),
        ('/usr/share/sounds/logout.wav', 2, 'dialog-error'),
        ('/usr/share/sounds/info.wav', 3, 'contact-new'),
        ('/usr/share/sounds/error.wav', 3, 'network-offline'),  # "network-error"
        ('/usr/share/sounds/info.wav', 2, 'emblem-new'),  # "appointment-new" 
        ('/usr/share/sounds/info.wav', 2, 'emblem-default'),  # "face-smile-big"
        ('/usr/share/sounds/info.wav', 2, 'dialog-error'),
        ('/usr/share/sounds/info.wav', 2, 'emblem-new'),
        ('/usr/share/sounds/info.wav', 2, 'emblem-new'),
    ]

    ALERT_STR_TO_ID = {
        "default": AUDIO_ALERT_DEFAULT,
        "notify": AUDIO_ALERT_NOTIFY,
        "warning": AUDIO_ALERT_WARNING,
        "critical": AUDIO_ALERT_CRITICAL,
        "network-online": AUDIO_ALERT_NETWORK_ONLINE,
        "network-offline": AUDIO_ALERT_NETWORK_OFFLINE,
        "signal-new": AUDIO_ALERT_SIGNAL_NEW,
        "trade-win": AUDIO_ALERT_TRADE_WIN,
        "trade-lost": AUDIO_ALERT_TRADE_LOST,
        "alert-up": AUDIO_ALERT_UP,
        "alert-down": AUDIO_ALERT_DOWN,
    }

    def __init__(self, identifier, service, options):
        super().__init__("desktop", identifier, service)

        self._backtesting = options.get('backtesting', False)

        notifier_config = service.notifier_config(identifier)

        # default audio alert and popups stats configurable
        self._audible = notifier_config.get('play-alerts', False)
        self._popups = notifier_config.get('display-popups', False)

        self._audio_device = notifier_config.get('audio-device', DesktopNotifier.DEFAULT_AUDIO_DEVICE)

        # map alerts
        self._alerts = copy.copy(DesktopNotifier.DEFAULT_ALERTS)
        alerts_config = notifier_config.get('alerts', {})

        for k, alert in alerts_config.items():
            alert_id = DesktopNotifier.ALERT_STR_TO_ID.get(k)
            if alert_id is not None:
                self._alerts[alert_id] = (alert[0], alert[1], alert[2])

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
        alert = None

        if Signal.SIGNAL_STRATEGY_SIGNAL_ENTRY <= signal.signal_type <= Signal.SIGNAL_STRATEGY_TRADE_UPDATE:
            icon = "contact-new"
            alert = DesktopNotifier.AUDIO_ALERT_SIGNAL_NEW

            if signal.data['way'] == "exit" and 'profit-loss' in signal.data:
                if signal.data['profit-loss'] < 0.0:
                    alert = DesktopNotifier.AUDIO_ALERT_TRADE_LOST
                    icon = self._alerts[alert][2]
                else:
                    alert = DesktopNotifier.AUDIO_ALERT_TRADE_WIN
                    icon = self._alerts[alert][2]

            ldatetime = datetime.fromtimestamp(signal.data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')

            # generic signal reason
            action = signal.data['way']

            # specified exit reason
            if action == "exit" and 'stats' in signal.data and 'exit-reason' in signal.data['stats']:
                action = signal.data['stats']['exit-reason']

            label = "Signal %s %s on %s" % (action, signal.data['direction'], signal.data['symbol'],)

            way = '>' if signal.data['way'] == "entry" else '<'
            exit_reason = signal.data['stats'].get('exit-reason', "") if 'stats' in signal.data else ""

            message = "%s@%s (%s) %s %s at %s - #%s in %s" % (
                signal.data['symbol'],
                signal.data['order-price'],
                signal.data['app-name'],
                action,
                signal.data['direction'],
                ldatetime,
                signal.data['id'],
                signal.data['timeframe'])

            if signal.data.get('stop-loss-price'):
                message += " SL@%s" % (signal.data['stop-loss-price'],)

            if signal.data.get('take-profit-price'):
                message += " TP@%s" % (signal.data['take-profit-price'],)

            if signal.data.get('profit-loss') is not None:
                message += " (%.2f%%)" % ((signal.data['profit-loss'] * 100),)

            if signal.data['label'] is not None:
                message += " (%s)" % signal.data['label']

        elif signal.signal_type == Signal.SIGNAL_STRATEGY_ALERT:
            icon = "emblem-new"
            alert = DesktopNotifier.AUDIO_ALERT_SIGNAL_NEW

            if signal.data['trigger'] > 0:
                alert = DesktopNotifier.AUDIO_ALERT_UP
                icon = self._alerts[alert][2]
            elif signal.data['trigger'] < 0:
                alert = DesktopNotifier.AUDIO_ALERT_DOWN
                icon = self._alerts[alert][2]

            ldatetime = datetime.fromtimestamp(signal.data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')

            label = "Alert %s %s on %s" % (signal.data['name'], signal.data['reason'], signal.data['symbol'],)

            message = "%s %s@%s (%s) %s at %s - #%s in %s" % (
                signal.data['name'],
                signal.data['symbol'],
                signal.data['last-price'],
                signal.data['app-name'],
                signal.data['reason'],
                ldatetime,
                signal.data['id'],
                signal.data['timeframe'])

            if signal.data['message'] is not None:
                message += " (%s)" % signal.data['message']

        elif signal.signal_type == Signal.SIGNAL_MARKET_SIGNAL:
            return

        elif signal.signal_type == Signal.SIGNAL_WATCHDOG_TIMEOUT:
            return

        elif signal.signal_type == Signal.SIGNAL_WATCHDOG_UNREACHABLE:
            return

        # process sound
        if not self._backtesting and self._audible and alert is not None:
            self.play_audio_alert(alert)

        if not self._backtesting and self._popups and message:
            if self.notify2:
                n = self.notify2.Notification(label, message, icon)
                n.show()

    def command(self, command_type, data):
        # @todo results
        if command_type == self.COMMAND_TOGGLE and data and data.get("value", "") == "popup":
            self._popups = not self._popups
            Terminal.inst().action("desktop notifier popups are now %s" % ("actives" if self._popups else "disabled",), view='status')
        elif command_type == self.COMMAND_TOGGLE and data and data.get("value", "") == "audible":
            self._audible = not self._audible
            Terminal.inst().action("desktop notifier audio alertes are now %s" % ("actives" if self._audible else "disabled",), view='status')
        elif command_type == self.COMMAND_INFO:
            Terminal.inst().info("desktop notifier is %s" % ("active" if self._playpause else "disabled",), view='content')

        return None

    def receiver(self, signal):
        if not self._playpause or self._backtesting or not signal:
            return

        if signal.source == Signal.SOURCE_STRATEGY:
            if Signal.SIGNAL_STRATEGY_SIGNAL_ENTRY <= signal.signal_type <= Signal.SIGNAL_STRATEGY_ALERT:
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
