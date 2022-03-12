# @date 2021-11-30
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# Strategy helper to get dataset

from common.utils import timeframe_to_str

import logging
logger = logging.getLogger('siis.strategy')
error_logger = logging.getLogger('siis.error.strategy')


def get_all_regions(strategy):
    """
    Generate and return an array of all the regions :
        symbol: str market identifier
        id: int region identifier
    """
    results = []

    with strategy._mutex:
        try:
            for k, strategy_trader in strategy._strategy_traders.items():
                with strategy_trader._mutex:
                    for region in strategy_trader.regions:
                        # check if inside
                        is_inside = region.test(strategy.timestamp, strategy_trader.instrument.market_price)

                        results.append({
                            'mid': strategy_trader.instrument.market_id,
                            'sym': strategy_trader.instrument.symbol,
                            'id': region._id,
                            'vers': region.version(),
                            'name': region.name(),
                            'dir': region.direction_to_str(),
                            'stage': region.stage_to_str(),
                            'ts': region._created,
                            'tf': timeframe_to_str(region._timeframe),
                            'expiry': region._expiry,
                            'cancel': region.cancellation_str(strategy_trader.instrument),
                            'inside': is_inside,
                            'cond': region.condition_str(strategy_trader.instrument),
                        })

        except Exception as e:
            error_logger.error(repr(e))

    return results
