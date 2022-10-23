# @date 2018-11-30
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Android notifier bot message post.

import time

from datetime import datetime, timedelta

from notifier.notifier import Notifier

from notifier.android.androidpush import send_to_android

from common.signal import Signal
from common.utils import timeframe_from_str

import logging
logger = logging.getLogger('siis.notifier.android')
error_logger = logging.getLogger('siis.error.notifier.android')


class AndroidNotifier(Notifier):
    """
    Android Firebase push notifier.

    @todo Strategy alert notifications
    @todo trade-quantity
    """

    def __init__(self, identifier: str, service, options: dict):
        super().__init__("android", identifier, service)

        self._backtesting = options.get('backtesting', False)

        notifier_config = service.notifier_config(identifier)

        self._who = notifier_config.get('who', 'SiiS')
        self._auth_key = notifier_config.get('auth-key')

        # @todo update targets channels
        self._channels = notifier_config.get('channels', {
            "trades": "/topics/default",
            "signals": "/topics/default",
            "watchdog": "/topics/default"
        })

        if 'signals' not in self._channels:
            self._channels['signals'] = "/topics/default"

        if 'watchdog' not in self._channels:
            self._channels['watchdog'] = "/topics/default"

        self._signals_opts = notifier_config.get('signals', (
                "alert",
                "trade-entry",
                "trade-exit",
                # "trade-update",
                "trade-error",
                "trade-quantity",
                'signal-entry',
                'signal-exit',
            ))

        self._watchdog = notifier_config.get('watchdog', ("timeout", "unreachable"))
        self._account = notifier_config.get('account', ("balance", "assets-balance"))

    def start(self, options):
        if self._backtesting:
            logger.warning("Notifier %s - %s : signals not started because of backtesting !" % (
                self.name, self.identifier))
            return False
        elif self._auth_key and self._channels.get('signals'):
            return super().start(options)
        else:
            return False

    def terminate(self):
        pass

    def notify(self):
        pass

    def process_signal(self, signal):
        message = ""
        locale = "fr"
        sound = "default"
        channel = ""

        if signal.signal_type == Signal.SIGNAL_STRATEGY_SIGNAL_ENTRY:
            if 'signal-entry' not in self._signals_opts:
                return

            channel = self._channels.get('signals')  # @todo

            messages = self.format_strategy_signal_entry(signal.data, locale)
            message = '\n'.join(messages)

        elif signal.signal_type == Signal.SIGNAL_STRATEGY_SIGNAL_EXIT:
            if 'signal-exit' not in self._signals_opts:
                return

            channel = self._channels.get('signals')  # @todo

            messages = self.format_strategy_signal_exit(signal.data, locale)
            message = '\n'.join(messages)

        elif signal.signal_type == Signal.SIGNAL_STRATEGY_TRADE_ENTRY:
            if 'trade-entry' not in self._signals_opts:
                return

            channel = self._channels.get('signals')  # @todo

            messages = self.format_trade_entry(signal.data, locale)
            message = '\n'.join(messages)

        elif signal.signal_type == Signal.SIGNAL_STRATEGY_TRADE_UPDATE:
            if 'trade-update' not in self._signals_opts:
                return

            # not supported
            # channel = self._channels.get('signals')  # @todo
            #
            # messages = self.format_trade_update(signal.data, locale)
            # message = '\n'.join(messages)

        elif signal.signal_type == Signal.SIGNAL_STRATEGY_TRADE_EXIT:
            if 'trade-exit' not in self._signals_opts:
                return

            channel = self._channels.get('signals')  # @todo

            messages = self.format_trade_exit(signal.data, locale)
            message = '\n'.join(messages)

        elif signal.signal_type == Signal.SIGNAL_STRATEGY_TRADE_ERROR:
            if 'trade-error' not in self._signals_opts:
                return

            channel = self._channels.get('signals')  # @todo

            messages = self.format_trade_error(signal.data, locale)
            message = '\n'.join(messages)

        elif signal.signal_type == Signal.SIGNAL_STRATEGY_ALERT:
            if 'alert' not in self._signals_opts:
                return

            channel = self._channels.get('signals')  # @todo

            messages = self.format_strategy_alert(signal.data, locale)
            message = '\n'.join(messages)

        elif signal.signal_type == Signal.SIGNAL_MARKET_SIGNAL:
            return

        elif signal.signal_type == Signal.SIGNAL_WATCHDOG_TIMEOUT:
            if 'timeout' not in self._watchdog:
                return

            channel = self._channels.get('watchdog')

            messages = self.format_watchdog_timeout(signal.data, locale)
            message = '\n'.join(messages)

        elif signal.signal_type == Signal.SIGNAL_WATCHDOG_UNREACHABLE:
            if 'unreachable' not in self._watchdog:
                return

            channel = self._channels.get('watchdog')

            messages = self.format_watchdog_unreachable(signal.data, locale)
            message = '\n'.join(messages)

        elif signal.signal_type == Signal.SIGNAL_DATA_TIMEOUT:
            if 'timeout' not in self._watchdog:
                return

            channel = self._channels.get('watchdog')

            messages = self.format_data_timeout(signal.data, locale)
            message = '\n'.join(messages)

        if message:
            if channel and self._auth_key:
                try:
                    send_to_android(self._auth_key, channel, self._who, message, sound)
                except:
                    pass

    def format_trade_entry(self, t, locale):
        messages = []

        if self._prefix:
            messages.append("%s event :" % self._prefix)

        trade_id = t['id']
        symbol = t['symbol']
        alias = t['alias']

        open_dt = Notifier.parse_utc_datetime(t['entry-open-time'])

        op = float(t.get('order-price', "0"))
        aep = float(t.get('avg-entry-price', "0"))

        order_type = t['stats']['entry-order-type']

        if self._template in ("default", "verbose"):
            messages.append("%s %s:%s [ NEW ]" % (t['direction'].capitalize(), alias or symbol, trade_id))
            messages.append("- %s: %s" % (order_type.title(), Notifier.format_datetime(open_dt, locale)))

            if aep:
                messages.append("- Entry-Price: %s" % t['avg-entry-price'])
            elif op:
                messages.append("- Order-Price: %s" % t['order-price'])

            if 'trade-quantity' in self._signals_opts and t['order-qty']:
                messages.append("- Amount: %s" % t['order-qty'])

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
            messages.append("%s %s:%s [ NEW ]" % (t['direction'].capitalize(), alias or symbol, trade_id))

            if aep:
                messages.append("- Entry-Price: %s" % t['avg-entry-price'])
            elif op:
                messages.append("- Entry-Price: %s" % t['order-price'])

            if 'trade-quantity' in self._signals_opts and t['order-qty']:
                messages.append("- Amount: %s" % t['order-qty'])

        if float(t['take-profit-price']):
            messages.append("- Take-Profit: %s" % t['take-profit-price'])
        if float(t['stop-loss-price']):
            messages.append("- Stop-Loss: %s" % t['stop-loss-price'])

        if t['comment']:
            messages.append('- Comment: %s' % t['comment'])

        return messages

    # def format_trade_update(self, t, locale):
    #     messages = []
    #
    #     if self._prefix:
    #         messages.append("%s event :" % self._prefix)
    #
    #     trade_id = t['id']
    #     symbol = t['symbol']
    #     alias = t['alias']
    #
    #     # filter only if a change occurs on targets or from entry execution state
    #     pt = self._opened_trades.get(symbol, {}).get(trade_id)
    #
    #     accept = False
    #     execute = False
    #     modify_tp = False
    #     modify_sl = False
    #     modify_comment = False
    #
    #     if pt:
    #         if pt['avg-entry-price'] != t['avg-entry-price']:
    #             accept = True
    #             execute = True
    #         if pt['take-profit-price'] != t['take-profit-price']:
    #             accept = True
    #             modify_tp = True
    #         if pt['stop-loss-price'] != t['stop-loss-price']:
    #             accept = True
    #             modify_sl = True
    #         if pt['comment'] != t['comment']:
    #             accept = True
    #             modify_comment = True
    #
    #     if accept:
    #         if self._template in ("default", "verbose"):
    #             if execute and float(t['avg-entry-price']):
    #                 messages.append("- Entry-Price: %s" % t['avg-entry-price'])
    #
    #         if modify_tp and float(t['take-profit-price']):
    #             messages.append("- Modify-Take-Profit: %s" % t['take-profit-price'])
    #         if modify_sl and float(t['stop-loss-price']):
    #             messages.append("- Modify-Stop-Loss: %s" % t['stop-loss-price'])
    #
    #         if modify_comment and t['comment']:
    #             messages.append("- Comment: %s" % t['comment'])
    #
    #         if messages:
    #             # prepend update message if there is some content to publish
    #             messages.insert(0, "%s %s:%s [ UPDATE ]" % (t['direction'].capitalize(), alias or symbol, trade_id))
    #
    #     return messages

    def format_trade_exit(self, t, locale):
        messages = []

        if self._prefix:
            messages.append("%s event :" % self._prefix)

        trade_id = t['id']
        symbol = t['symbol']
        alias = t['alias']
        market_id = t['market-id']

        axp = float(t.get('avg-exit-price', "0"))

        messages.append("%s %s:%s [ CLOSE ]" % (t['direction'].capitalize(), alias or symbol, trade_id))

        if axp:
            messages.append("- Exit-Price: %s" % t['avg-exit-price'])

        if t['stats']['exit-reason'] != "undefined":
            messages.append("- Cause: %s" % t['stats']['exit-reason'].title())

        if t['profit-loss-pct'] > 0.0 and self._display_percent_win:
            if self._display_percent_in_pip:
                instrument = self.service.strategy_service.strategy().instrument(market_id)
                messages.append("- Reward : %gpips" % Notifier.pnl_in_pips(instrument, t))
            else:
                messages.append("- Reward : %.2f%%" % t['profit-loss-pct'])
        elif t['profit-loss-pct'] < 0.0 and self._display_percent_loss:
            if self._display_percent_in_pip:
                instrument = self.service.strategy_service.strategy().instrument(market_id)
                messages.append("- Loss : %gpips" % Notifier.pnl_in_pips(instrument, t))
            else:
                messages.append("- Loss : %.2f%%" % t['profit-loss-pct'])

        return messages

    def format_trade_error(self, t, locale):
        messages = []

        if self._prefix:
            messages.append("%s event :" % self._prefix)

        fmt_datetime = datetime.fromtimestamp(t['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        messages.append("Trade error at %s - #%s on %s" % (fmt_datetime, t['trade-id'], t['symbol']))

        return messages

    def format_strategy_signal_entry(self, s, locale):
        messages = []

        if self._prefix:
            messages.append("%s event :" % self._prefix)

        signal_id = s['id']
        symbol = s['symbol']
        alias = s.get('alias')

        signal_dt = Notifier.parse_utc_datetime(s['entry-open-time'] or s['timestamp'])

        op = float(s.get('order-price', "0"))

        order_type = s['order-type']

        if self._template in ("default", "verbose"):
            messages.append("%s %s:%s [ SIG-ENTRY ]" % (s['direction'].capitalize(), alias or symbol, signal_id))
            messages.append("- %s: %s" % (order_type.title(), Notifier.format_datetime(signal_dt, locale)))

            if op:
                messages.append("- Order-Price: %s" % s['order-price'])

            if s['timeframe']:
                messages.append("- Timeframe: %s" % s['timeframe'])

            if s['label']:
                messages.append("- Context: %s" % s['label'])

            if s['entry-timeout']:
                et_tf = timeframe_from_str(s['entry-timeout'])
                if et_tf > 0.0:
                    entry_timeout_dt = signal_dt + timedelta(seconds=et_tf)
                    messages.append("- Cancel entry after : %s" % Notifier.format_datetime(entry_timeout_dt))

            if s['expiry']:
                expiry_dt = signal_dt + timedelta(seconds=s['expiry'])
                messages.append("- Close expiry after : %s" % Notifier.format_datetime(expiry_dt))

        elif self._template == "light":
            messages.append("%s %s:%s [ SIG-ENTRY ]" % (s['direction'].capitalize(), alias or symbol, signal_id))

            if op:
                messages.append("- Entry-Price: %s" % s['order-price'])

        if float(s['take-profit-price']):
            messages.append("- Take-Profit: %s" % s['take-profit-price'])
        if float(s['stop-loss-price']):
            messages.append("- Stop-Loss: %s" % s['stop-loss-price'])

        return messages

    def format_strategy_signal_exit(self, s, locale):
        messages = []

        if self._prefix:
            messages.append("%s event :" % self._prefix)

        signal_id = s['id']
        symbol = s['symbol']
        alias = s.get('alias')

        signal_dt = Notifier.parse_utc_datetime(s['exit-open-time'] or s['timestamp'])

        if self._template in ("default", "verbose"):
            messages.append("%s %s:%s [ SIG-EXIT ]" % (s['direction'].capitalize(), alias or symbol, signal_id))
            messages.append("- %s: %s" % ("Market", Notifier.format_datetime(signal_dt, locale)))

            if s['timeframe']:
                messages.append("- Timeframe: %s" % s['timeframe'])

            if s['label']:
                messages.append("- Context: %s" % s['label'])

        elif self._template == "light":
            messages.append("%s %s:%s [ SIG-EXIT ]" % (s['direction'].capitalize(), alias or symbol, signal_id))

        if float(s['take-profit-price']):
            messages.append("- Take-Profit: %s" % s['take-profit-price'])
        if float(s['stop-loss-price']):
            messages.append("- Stop-Loss: %s" % s['stop-loss-price'])

        return messages

    def format_strategy_alert(self, a, locale):
        messages = []

        if self._prefix:
            messages.append("%s event :" % self._prefix)

        fmt_datetime = datetime.fromtimestamp(a['timestamp']).strftime('%Y-%m-%d %H:%M:%S')

        if a['trigger'] > 0:
            notification_type = "Alert-up"
        elif a['trigger'] < 0:
            notification_type = "Alert-down"
        else:
            notification_type = "Alert"

        messages.append("%s on %s" % (notification_type, fmt_datetime))
        messages.append("%s %s@%s %s" % (a['name'], a['symbol'], a['last-price'], a['reason']))
        messages.append("#%s in %s" % (a['id'], a['timeframe']))

        if a.get('message'):
            messages.append("Msg: %s" % a['message'])

        return messages

    def format_watchdog_timeout(self, d, locale):
        messages = []

        if self._prefix:
            messages.append("%s event :" % self._prefix)

        fmt_datetime = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
        messages.append("Watchdog timeout pid %i service %s after %.0f' at %s" % (d[0], d[1], d[2], fmt_datetime))

        return messages

    def format_watchdog_unreachable(self, d, locale):
        messages = []

        if self._prefix:
            messages.append("%s event :" % self._prefix)

        fmt_datetime = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
        messages.append("Watchdog unreachable service %s at %s - %s" % (d[0], fmt_datetime, d[1]))

        return messages

    def format_data_timeout(self, d, locale):
        messages = []

        if self._prefix:
            messages.append("%s event :" % self._prefix)

        fmt_datetime = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
        messages.append("Watchdog data timeout type %s detail %s since %.0f' at %s" % (d[0], d[1], d[2], fmt_datetime))

        return messages

    def receiver(self, signal):
        if not self._playpause or self._backtesting or not signal:
            return

        if signal.source == Signal.SOURCE_STRATEGY:
            if Signal.SIGNAL_STRATEGY_SIGNAL_ENTRY <= signal.signal_type <= Signal.SIGNAL_STRATEGY_ALERT:
                self.push_signal(signal)
            elif signal.signal_type == Signal.SIGNAL_DATA_TIMEOUT:
                self.push_signal(signal)

        elif signal.source == Signal.SOURCE_WATCHDOG:
            if Signal.SIGNAL_WATCHDOG_TIMEOUT <= signal.signal_type <= Signal.SIGNAL_WATCHDOG_UNREACHABLE:
                self.push_signal(signal)
            elif signal.signal_type == Signal.SIGNAL_DATA_TIMEOUT:
                self.push_signal(signal)

        elif signal.source == Signal.SOURCE_TRADER:
            if signal.signal_type == Signal.SIGNAL_DATA_TIMEOUT:
                self.push_signal(signal)
