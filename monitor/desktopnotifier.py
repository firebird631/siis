# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Desktop notification handler

import collections
import threading
import os
import time
import notify2
import logging
import subprocess
import traceback

from datetime import datetime, timedelta

from trader.position import Position
from monitor.discord.webhooks import send_to_discord

from notifier.notifiable import Notifiable
from notifier.signal import Signal

from terminal.terminal import Terminal
from database.database import Database

from common.utils import timeframe_to_str


class DesktopNotifier(Notifiable):
    """
    Desktop + audible notification from some particulars signals.

    @todo seperate module and as a service + instance : one for the desktop, one for the terminal views, one for the email, one discord, to avoid blocking
    @todo config
    @todo the discord notifier part had to move to a DiscordNotifier module
    @todo add alert when trade operation is processed
    """

    AUDIO_ALERT_SIMPLE = 0
    AUDIO_ALERT_INTENSIVE = 1
    AUDIO_ALERT_WARNING = 2
    AUDIO_ALERT_HAPPY = 3

    def __init__(self):
        super().__init__("desktop")

        self.strategy_service = None
        self.trader_service = None
        self.watcher_service = None

        self.last_notify = 0
        self.audible = False
        self.popups = False
        self.discord = False

        self._mutex = threading.RLock()  # reentrant locker
        self._signals = collections.deque()  # filtered received signals

        self._last_stats = 0

        self._last_strategy_view = 0
        self._displayed_strategy = 0

        self._discord_webhook = {
            'signals': 'https://discordapp.com/api/webhooks/539501969862295557/FMQTMhUQbhxow5EPW_2G8YKBPVtpqHEJDczzA2yW5OeQKXVjJKuRZe4ILMPcGEfYZaiq',
            'altusdt-15m-reports': 'https://discordapp.com/api/webhooks/549002302602870785/usiI7sYPCPm0zcI7Af3OEEpSpH4M0GzCKkL6xfgVgKmIObGRvi8mCSFcY6vusAPDeN5L',
            'altbtc-15m-reports': 'https://discordapp.com/api/webhooks/549002507763056641/vpPVbeFpd3wVbgecx0AmKKgCeCQ6Cu1SvzxUDD82CodAblI1FWxfFIa1vHQ65IpblPMk',
            'forex-15m-reports': 'https://discordapp.com/api/webhooks/549002507763056641/vpPVbeFpd3wVbgecx0AmKKgCeCQ6Cu1SvzxUDD82CodAblI1FWxfFIa1vHQ65IpblPMk',
            'daily-reports': 'https://discordapp.com/api/webhooks/542848229859917834/PyGUjiTmRlSd8j7AtNh-sWef38ZbIQuSxMWQA8VgLMzuPKuV2fvGr3z44B5JFkpQeBNJ',
            'weekly-reports': 'https://discordapp.com/api/webhooks/542848303281471504/rC9BKhsygiLgAUhTS2JpPSscpVdPn69qJcWMHUZbTacPArFRmDyM4Dt8qmjJLgt5iCLY',
            'bitmex-crystalball': 'https://discordapp.com/api/webhooks/567346875070677034/83LuKTcMEd5ja6CLQId2u9CnR52L405ir2FPFbIvO52McJxKcqHzUdKSEJgaA6gsopt-',
            'binance-crystalball': 'https://discordapp.com/api/webhooks/567346955630542869/wSltI4G5QUKfG0D1-4THXjvRTnn1s4LVqFqNik7QWmr_ZWl7eCCpPxUxIA-1y5heC5sr',
        }

        self._alerts = [
            ('/usr/share/sounds/info.wav', 3),
            ('/usr/share/sounds/phone.wav', 2),
            ('/usr/share/sounds/error.wav', 5),
            ('/usr/share/sounds/logout.wav', 1)
        ]

        self._audio_device = 'pulse'

        # lib notify
        notify2.init('SiiS')      

    def lock(self, blocking=True, timeout=-1):
        self._mutex.acquire(blocking, timeout)

    def unlock(self):
        self._mutex.release()

    def on_key_pressed(self, key):
        if key == 'KEY_SPREVIOUS':
            self.prev_item()
        elif key == 'KEY_SNEXT':
            self.next_item()
        elif key in ('KEY_SR', 'KEY_SF', 'KEY_SLEFT', 'KEY_SRIGHT', 'KEY_PPAGE', 'KEY_NPAGE'):
            self._last_strategy_view = 0  # force refresh

    def prev_item(self):
        self._displayed_strategy -= 1
        if self._displayed_strategy < 0:
            self._displayed_strategy = 0

        self._last_strategy_view = 0  # force refresh

    def next_item(self):
        self._displayed_strategy += 1
        self._last_strategy_view = 0  # force refresh

    def receiver(self, signal):
        if signal.signal_type in (
                Signal.SIGNAL_SOCIAL_ENTER, Signal.SIGNAL_SOCIAL_EXIT, Signal.SIGNAL_STRATEGY_ENTRY_EXIT):

            # not during a backtesting
            if self.strategy_service and self.strategy_service.backtesting:
                return

            self._signals.append(signal)

    def update(self):
        count = 0

        while self._signals:
            signal = self._signals.popleft()

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
                    continue

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
                    continue

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

                if signal.data['rate'] is not None:
                    message += " (%.2f%%)" % ((signal.data['rate'] * 100),)

                if self.discord:
                    if signal.data['identifier'] in self._discord_webhook:
                        send_to_discord(self._discord_webhook[signal.data['identifier']], 'CryptoBot', '```' + message + '```')
                    else:
                        send_to_discord(self._discord_webhook['signals'], 'CryptoBot', '```' + message + '```')

                # log them to the content view
                Terminal.inst().notice(label, view="content")
                Terminal.inst().notice(message, view="content")

            # elif signal.signal_type == Signal.SIGNAL_STRATEGY_MODIFY:
            #     pass

            # process sound
            if self.audible and audio_alert:
                # if repeat
                for i in range(0, self._alerts[audio_alert[1]]):
                    subprocess.Popen(['aplay', '-D', self._audio_device, self._alerts[audio_alert[0]]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                # duration = 1  # second
                # freq = 440  # Hz
                # os.system('play --no-show-progress --null --channels 1 synth %s sine %f' % (duration, freq))

            if self.popups and message:
                n = notify2.Notification(
                    label,
                    message,
                    icon)

                n.show()

            count += 1
            if count > 10:
                # no more than per loop
                break

        # time.sleep(0.001)  # its sync to main thread no need more

    def terminate(self):
        notify2.uninit()

    def sync(self):
        # synced update
        self.update()

        if self.strategy_service:
            # discord 15m reports

            # if self.discord and time.time() - self._last_stats >= 15*60:  # every 15m
            #     if self.send_discord():
            #         self._last_stats = time.time()

            # strategy stats
            if time.time() - self._last_strategy_view >= 0.5:  # every 0.5 second, refresh
                self.refresh_stats()
                self._last_strategy_view = time.time()

    def send_discord(self):
        # @todo must be in a specific discordnotifier
        for strategy in self.strategy_service.get_appliances():
            results = strategy.get_stats()
            dst = None

            if 'altusdt' in strategy.identifier:
                dst = self._discord_webhook['altusdt-15m-reports']
            elif 'altbtc' in strategy.identifier:
                dst = self._discord_webhook['altbtc-15m-reports']
            elif 'forex' in strategy.identifier:
                dst = self._discord_webhook['forex-15m-reports']

            if results:
                arr1, arr2 = strategy.formatted_stats(results, style='')

                self.split_and_send(dst, arr1)
                self.split_and_send(dst, arr2)

        return True

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
                send_to_discord(dst, 'Bot', '```' + buf + '```')

    def refresh_stats(self):
        self.refresh_strategies_stats()
        self.refresh_traders_stats()

    def refresh_strategies_stats(self):
        # @todo must be in distinct View
        if not self.strategy_service:
            return

        if not (Terminal.inst().is_active('strategy') or Terminal.inst().is_active('perf') or Terminal.inst().is_active('stats')):
            return

        appliances = appl = self.strategy_service.get_appliances()
        if self._displayed_strategy >= len(appliances):
            self._displayed_strategy = 0

        appl = None

        if not appliances:
            return

        appl = self.strategy_service.get_appliances()[self._displayed_strategy]

        if not appl:
            return

        if Terminal.inst().is_active('strategy') or Terminal.inst().is_active('perf'):
            results = appl.get_stats()

            # tabular formated text
            arr1, arr2 = appl.formatted_stats(results, style=Terminal.inst().style(), quantities=True)

            # perf view
            if Terminal.inst().is_active('perf'):
                Terminal.inst().info("Perf per market trades for strategy %s - %s" % (appl.name, appl.identifier), view='perf-head')
                Terminal.inst().info(arr1, view='perf')

            # strategy view
            if Terminal.inst().is_active('strategy'):
                Terminal.inst().info("Active trades for strategy %s - %s" % (appl.name, appl.identifier), view='strategy-head')
                Terminal.inst().info(arr2, view='strategy')

        # stats view
        if Terminal.inst().is_active('stats'):
            Terminal.inst().info("Trade history for strategy %s - %s" % (appl.name, appl.identifier), view='stats-head')

            results = appl.get_history_stats(0, 50, None)

            # tabular formated text
            arr = appl.formatted_trade_stats(results, style=Terminal.inst().style(), quantities=True)

            try:
                Terminal.inst().info(arr, view='stats')
            except:
                pass

    def refresh_traders_stats(self):
        if not self.trader_service:
            return

        # account view
        if Terminal.inst().is_active('account'):
            traders = self.trader_service.get_traders()

            if len(traders) > 0:
                trader = next(iter(traders))

                Terminal.inst().info("Account details for trader %s - %s" % (trader.name, trader.account.name), view='account-head')

                try:
                    columns, table, total_size = trader.account_table(*Terminal.inst().active_content().format())
                    Terminal.inst().table(columns, table, total_size, view='account')
                except:
                    pass

        # tickers view
        if Terminal.inst().is_active('ticker'):
            traders = self.trader_service.get_traders()

            if len(traders) > 0:
                trader = next(iter(traders))

                Terminal.inst().info("Tickers list for tader %s on account %s" % (trader.name, trader.account.name), view='ticker-head')

                try:
                    columns, table, total_size = trader.markets_tickers_table(*Terminal.inst().active_content().format())
                    Terminal.inst().table(columns, table, total_size, view='ticker')
                except:
                    pass

        # markets view
        if Terminal.inst().is_active('market'):
            traders = self.trader_service.get_traders()

            if len(traders) > 0:
                trader = next(iter(traders))

                Terminal.inst().info("Market list trader %s on account %s" % (trader.name, trader.account.name), view='market-head')

                try:
                    columns, table, total_size = trader.markets_table(*Terminal.inst().active_content().format())
                    Terminal.inst().table(columns, table, total_size, view='market')
                except:
                    pass

        # assets view
        if Terminal.inst().is_active('asset'):
            traders = self.trader_service.get_traders()

            if len(traders) > 0:
                trader = next(iter(traders))

                Terminal.inst().info("Asset list trader %s on account %s" % (trader.name, trader.account.name), view='asset-head')

                try:
                    columns, table, total_size = trader.assets_table(*Terminal.inst().active_content().format())
                    Terminal.inst().table(columns, table, total_size, view='asset')
                except:
                    pass
