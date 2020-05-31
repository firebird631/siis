# @date 2020-05-30
# @author Frederic SCHERMA
# @license Copyright (c) 2020 Dream Overflow
# Strategy helper to get actives alertes dataset

from common.utils import timeframe_to_str

import logging
logger = logging.getLogger('siis.strategy')
error_logger = logging.getLogger('siis.error.strategy')


def get_all_active_alerts(strategy):
    """
    Generate and return an array of all the actives alertes :
        symbol: str market identifier
        id: int alert identifier
    """
    results = []
    trader = strategy.trader()

    with strategy._mutex:
        try:
            for k, strategy_trader in strategy._strategy_traders.items():
                with strategy_trader._mutex:
                    for alert in strategy_trader.alerts:
                        results.append({
                            'mid': strategy_trader.instrument.market_id,
                            'id': alert._id,
                            'vers': alert.version(),
                            'name': alert.name(),
                            'ts': alert._created,
                            'tf': timeframe_to_str(alert._timeframe),
                            'expiry': alert._expiry,
                            'ctd': alert._countdown,
                            'msg': alert._message,
                            'cond': alert.condition_str(),
                            'cancel': alert.cancelation_str(),
                        })

        except Exception as e:
            error_logger.error(repr(e))

    return results
