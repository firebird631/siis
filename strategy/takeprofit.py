# @date 2019-09-12
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Base strategy take profit methods

import numpy as np

from .strategytradercontext import StrategyTraderContext

import logging
logger = logging.getLogger('siis.strategy.takeprofit')


def search_std_atrsr(direction, sub, orientation, depth, price, epsilon=0.0):
    if not sub.atrsr:
        return 0.0

    if orientation > 0:
        return sub.atrsr.search_up(direction, price, depth, epsilon)
    elif orientation < 0:
        return sub.atrsr.search_down(direction, price, depth, epsilon)
    else:
        return sub.atrsr.search_both(direction, price, depth, epsilon)


def search_sorted_atrsr(direction, sub, orientation, depth, price, epsilon=0.0):
    if not sub.atrsr:
        return 0.0

    if orientation > 0:
        return sub.atrsr.search_sorted_up(direction, price, depth, epsilon)
    elif orientation < 0:
        return sub.atrsr.search_sorted_down(direction, price, depth, epsilon)
    else:
        return sub.atrsr.search_sorted_both(direction, price, depth, epsilon)

search_atrsr = search_std_atrsr
# search_atrsr = search_sorted_atrsr


def compute_take_profit(direction, data, sub, entry_price, confidence=1.0, price_epsilon=0.0):
    def compute_distance():
        if direction > 0:
            # never larger than distance in percent if defined
            if data.take_profit.distance_type == StrategyTraderContext.DIST_PERCENTILE:
                return entry_price * (1.0 + data.take_profit.distance)
            elif data.take_profit.distance_type == StrategyTraderContext.DIST_PRICE:
                return entry_price + data.take_profit.distance

        elif direction < 0:
            # never larger than distance in percent if defined
            if data.take_profit.distance_type == StrategyTraderContext.DIST_PERCENTILE:
                return entry_price * (1.0 - data.take_profit.distance)
            elif data.take_profit.distance_type == StrategyTraderContext.DIST_PRICE:
                return entry_price - data.take_profit.distance

            return 0.0

    if direction > 0:
        min_dist = 1.0 + data.min_profit

        if data.take_profit.type == data.PRICE_NONE:
            return 0.0

        elif data.take_profit.type == data.PRICE_ATR_SR:
            atr_take_profit = search_atrsr(direction, sub, data.take_profit.orientation,
                                           data.take_profit.depth, entry_price, price_epsilon)

            if data.take_profit.distance > 0.0:
                # never lesser than distance in percent if defined
                distance_take_profit = compute_distance()

                # if no ATR found return the fixed one, else return the higher
                if atr_take_profit <= 0.0:
                    return distance_take_profit

                return max(atr_take_profit, distance_take_profit)

            return atr_take_profit

        elif data.take_profit.type == data.PRICE_CUR_ATR_SR:
            curatr_take_profit = sub.atrsr.cur_up

            if data.take_profit.distance > 0.0:
                # never lesser than distance in percent if defined
                distance_take_profit = compute_distance()

                # if no current ATR return the fixed one, else return the higher
                if curatr_take_profit <= 0.0:
                    return distance_take_profit

                return max(curatr_take_profit, distance_take_profit)

            return curatr_take_profit

        elif data.take_profit.type == data.PRICE_BOLLINGER:
            if not sub.bollinger or not len(sub.bollinger.tops):
                return entry_price * min_dist

            tp = sub.bollinger.tops[-1]

            return max(tp, entry_price * min_dist)

        elif data.take_profit.type == data.PRICE_FIXED and data.take_profit.distance > 0.0:
            if data.take_profit.distance_type == data.DIST_PERCENTILE:
                return entry_price * (1.0 + data.take_profit.distance)
            elif data.take_profit.distance_type == data.DIST_PRICE:
                return entry_price + data.take_profit.distance

    elif direction < 0:
        min_dist = 1.0 - data.min_profit

        if data.take_profit.type == data.PRICE_NONE:
            return 0.0

        elif data.take_profit.type == data.PRICE_ATR_SR:
            atr_take_profit = search_atrsr(direction, sub, -data.take_profit.orientation,
                                           data.take_profit.depth, entry_price, price_epsilon)

            if data.take_profit.distance > 0.0:
                # never lesser than distance in percent if defined
                distance_take_profit = compute_distance()

                if atr_take_profit <= 0.0:
                    # if no ATR found return the fixed one
                    return distance_take_profit

                return min(atr_take_profit, distance_take_profit)

            return atr_take_profit

        elif data.take_profit.type == data.PRICE_CUR_ATR_SR:
            curatr_take_profit = sub.atrsr.cur_down

            if data.take_profit.distance > 0.0:
                # never lesser than distance in percent if defined
                distance_take_profit = compute_distance()

                if curatr_take_profit <= 0.0:
                    # if no ATR found return the fixed one
                    return distance_take_profit

                return min(curatr_take_profit, distance_take_profit)

            return curatr_take_profit

        elif data.take_profit.type == data.PRICE_BOLLINGER:
            if not sub.bollinger or not len(sub.bollinger.bottoms):
                return entry_price * min_dist

            tp = sub.bollinger.bottoms[-1]

            return min(tp, entry_price * min_dist)

        elif data.take_profit.type == data.PRICE_FIXED and data.take_profit.distance > 0.0:
            if data.take_profit.distance_type == data.DIST_PERCENTILE:
                return entry_price * (1.0 - data.take_profit.distance)
            elif data.take_profit.distance_type == data.DIST_PRICE:
                return entry_price - data.take_profit.distance

    return 0.0


def dynamic_take_profit_fixed_bollinger_long(sub, last_price, curr_take_profit_price, price_epsilon):
    take_profit = 0.0

    if sub.bollinger and len(sub.bollinger.tops) > 0:
        p = sub.bollinger.tops[-1]

        if p > curr_take_profit_price and p - price_epsilon > last_price:
            take_profit = p - price_epsilon

    return take_profit


def dynamic_take_profit_fixed_bollinger_short(sub, last_price, curr_take_profit_price, price_epsilon):
    take_profit = 0.0

    if sub.bollinger and len(sub.bollinger.bottoms) > 0:
        p = sub.bollinger.bottoms[-1]

        if p < curr_take_profit_price and p + price_epsilon < last_price:
            take_profit = p + price_epsilon

    return take_profit


def dynamic_take_profit_fixed_pct_long(sub, last_price, curr_take_profit_price, distance):
    take_profit = 0.0

    p = last_price * (1.0 + distance)

    if p > curr_take_profit_price and p > last_price:
        take_profit = p

    return take_profit


def dynamic_take_profit_fixed_pct_short(sub, last_price, curr_take_profit_price, distance):
    take_profit = 0.0

    p = last_price * (1.0 - distance)

    if p < curr_take_profit_price and p < last_price:
        take_profit = p

    return take_profit


def dynamic_take_profit_fixed_dist_long(sub, last_price, curr_take_profit_price, distance):
    take_profit = 0.0

    p = last_price + distance

    if p > curr_take_profit_price and p > last_price:
        take_profit = p

    return take_profit


def dynamic_take_profit_fixed_dist_short(sub, last_price, curr_take_profit_price, distance):
    take_profit = 0.0

    p = last_price - distance

    if p < curr_take_profit_price and p < last_price:
        take_profit = p

    return take_profit


def dynamic_take_profit_atrsr_long(sub, last_price, curr_take_profit_price, depth,
                                   orientation, price_epsilon=0.0):
    # search in short direction because we want a price lower than actual take-profit loss but we keep it
    # only if higher than current close price
    take_profit = search_atrsr(1, sub, orientation, depth, curr_take_profit_price, price_epsilon)

    if 0 < take_profit > last_price + price_epsilon:
        logger.debug("%s << %s" % (curr_take_profit_price, take_profit))
        return take_profit

    return 0.0

    # # or simply
    # take_profit = search_atrsr(1, sub, orientation, depth, curr_take_profit_price, price_epsilon)

    # if take_profit > last_price + price_epsilon and take_profit > curr_take_profit_price:
    #     return take_profit

    # return 0.0


def dynamic_take_profit_atrsr_short(sub, last_price, curr_take_profit_price, depth,
                                    orientation, price_epsilon=0.0):
    # reverse explanation of the long version (revert orientation)
    take_profit = search_atrsr(-1, sub, -orientation, depth, curr_take_profit_price, price_epsilon)

    if 0 < take_profit < last_price - price_epsilon:
        logger.debug("%s >> %s" % (curr_take_profit_price, take_profit))
        return take_profit

    return 0.0

    # or simply (revert orientation)
    # take_profit = search_atrsr(-1, sub, -orientation, depth, curr_take_profit_price, price_epsilon)

    # if take_profit > last_price - price_epsilon and take_profit < curr_take_profit_price:
    #     return take_profit

    # return 0.0


def dynamic_take_profit_cur_atrsr_long(sub, entry_price, last_price, curr_take_profit_price, depth,
                                       orientation, price_epsilon=0.0):
    take_profit = 0.0

    if sub.atrsr and len(sub.atrsr._tup):
        if sub.atrsr._tup[-1] > curr_take_profit_price and sub.atrsr._tup[-1] > entry_price:
            take_profit = sub.atrsr._tup[-1]

    if take_profit > last_price + price_epsilon:
        return take_profit

    return 0.0


def dynamic_take_profit_cur_atrsr_short(sub, entry_price, last_price, curr_take_profit_price, depth,
                                        orientation, price_epsilon=0.0):
    take_profit = 0.0

    if sub.atrsr and len(sub.atrsr._tdn):
        if sub.atrsr._tdn[-1] < curr_take_profit_price and sub.atrsr._tdn[-1] < entry_price:
            take_profit = sub.atrsr._tdn[-1]

    if take_profit < last_price - price_epsilon:
        return take_profit

    return 0.0


def dynamic_take_profit(direction, data, sub, entry_price, last_price, curr_take_profit_price, price_epsilon=0.0):

    if direction > 0:
        if data.type == StrategyTraderContext.PRICE_NONE:
            return 0.0

        elif data.type == StrategyTraderContext.PRICE_ATR_SR:
            return dynamic_take_profit_atrsr_long(sub, last_price, curr_take_profit_price, data.depth,
                                                  data.orientation, price_epsilon)

        elif data.type == StrategyTraderContext.PRICE_CUR_ATR_SR:
            return dynamic_take_profit_cur_atrsr_long(sub, entry_price, last_price, curr_take_profit_price,
                                                      data.depth, data.orientation, price_epsilon)

        elif data.type == StrategyTraderContext.PRICE_BOLLINGER:
            return dynamic_take_profit_fixed_bollinger_long(sub, last_price, curr_take_profit_price,
                                                            price_epsilon)

        elif data.type == StrategyTraderContext.PRICE_FIXED and data.distance > 0.0:
            if data.distance_type == StrategyTraderContext.DIST_PERCENTILE:
                return dynamic_take_profit_fixed_pct_long(sub, last_price, curr_take_profit_price, data.distance)
            elif data.distance_type == StrategyTraderContext.DIST_PRICE:
                return dynamic_take_profit_fixed_dist_long(sub, last_price, curr_take_profit_price, data.distance)

    elif direction < 0:
        if data.type == StrategyTraderContext.PRICE_NONE:
            return 0.0

        elif data.type == StrategyTraderContext.PRICE_ATR_SR:
            return dynamic_take_profit_atrsr_short(sub, last_price, curr_take_profit_price, data.depth,
                                                   data.orientation, price_epsilon)

        elif data.type == StrategyTraderContext.PRICE_CUR_ATR_SR:
            return dynamic_take_profit_cur_atrsr_short(sub, entry_price, last_price, curr_take_profit_price,
                                                       data.depth, data.orientation, price_epsilon)

        elif data.type == StrategyTraderContext.PRICE_BOLLINGER:
            return dynamic_take_profit_fixed_bollinger_short(sub, last_price, curr_take_profit_price,
                                                             price_epsilon)

        elif data.type == StrategyTraderContext.PRICE_FIXED and data.distance > 0.0:
            if data.distance_type == StrategyTraderContext.DIST_PERCENTILE:
                return dynamic_take_profit_fixed_pct_short(sub, last_price, curr_take_profit_price, data.distance)
            elif data.distance_type == StrategyTraderContext.DIST_PRICE:
                return dynamic_take_profit_fixed_dist_short(sub, last_price, curr_take_profit_price, data.distance)

    return 0.0
