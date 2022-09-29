import logging
import time
import threading

from common.signal import Signal


class ConnCheckerScript(threading.Thread):
    TRADER_CHECK_DELAY = 60.0

    TRADES_MAX_DELAY = 5*60.0
    TICKER_MAX_DELAY = 60.0

    SLEEP_TIME = 60.0

    def __init__(self, strategy_service, trader_service, unmanaged=False):
        super().__init__()

        self._strategy_service = strategy_service
        self._trader_service = trader_service

        self._trader_last_time = 0.0

        self._process = True
        self._unmanaged = unmanaged

    def run(self):
        while self._process:
            now = time.time()
            if now - self._trader_last_time >= ConnCheckerScript.TRADER_CHECK_DELAY:
                self._trader_last_time = now

                if self._trader_service.trader():
                    errors = []
                    timestamp = time.time()

                    trader = self._trader_service.trader()
                    with trader.mutex:
                        for market_id, market in trader._markets.items():
                            if time.time() - market.last_update_time > ConnCheckerScript.TICKER_MAX_DELAY:
                                errors.append(("trader.ticker", market_id, market.last_update_time))
                                timestamp = min(timestamp, market.last_update_time)

                            if time.time() - market.last_trade_timestamp > ConnCheckerScript.TRADES_MAX_DELAY:
                                errors.append(("trader.trades", market_id, market.last_trade_timestamp))
                                timestamp = min(timestamp, market.last_trade_timestamp)

                    if errors:
                        # notify in the name of the trader service
                        if len(errors) <= 2:
                            for error in errors:
                                self._trader_service.notify(Signal.SIGNAL_DATA_TIMEOUT, trader.name, error)
                        else:
                            self._trader_service.notify(Signal.SIGNAL_DATA_TIMEOUT, trader.name, (
                                "trader", "ticker/trades", timestamp))

            if self._unmanaged and self._strategy_service.strategy() is None:
                # conditional break for older version
                self._process = False
                break

            time.sleep(ConnCheckerScript.SLEEP_TIME)

    def stop(self):
        self._process = False
        super().join(10)


def run_once(watcher_service, trader_service, strategy_service, monitor_service, notifier_service):
    results = {
        'messages': [],
        'error': False
    }

    results['messages'].append("Install cron trade connection checker")

    if hasattr(monitor_service, 'install_script'):
        if not monitor_service.has_script('conn-checker'):
            monitor_service.install_script('conn-checker', ConnCheckerScript(strategy_service, trader_service))
    else:
        # for older version
        try:
            instance = ConnCheckerScript(strategy_service, trader_service, True)
            instance.start()
        except Exception as e:
            results['error'] = True
            results['messages'].append(repr(e))

    return results


def remove(watcher_service, trader_service, strategy_service, monitor_service, notifier_service):
    results = {
        'messages': [],
        'error': False
    }

    results['messages'].append("Stop and remove cron trade connection checker")

    if hasattr(monitor_service, 'remove_script'):
        if monitor_service.has_script('conn-checker'):
            monitor_service.remove_script('conn-checker')

    return results
