# @date 2019-09-12
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Base strategy take profit methods

import numpy as np

from .strategytradercontext import StrategyTraderContext


def search_std_atrsr(direction, timeframe, orientation, depth, price, epsilon=0.0):
    if not timeframe.atrsr:
        return 0.0

    if orientation > 0:
        return timeframe.atrsr.search_up(direction, price, depth, epsilon)
    elif orientation < 0:
        return timeframe.atrsr.search_down(direction, price, depth, epsilon)
    else:
        return timeframe.atrsr.search_both(direction, price, depth, epsilon)


def search_sorted_atrsr(direction, timeframe, orientation, depth, price, epsilon=0.0):
    if not timeframe.atrsr:
        return 0.0

    if orientation > 0:
        return timeframe.atrsr.search_sorted_up(direction, price, depth, epsilon)
    elif orientation < 0:
        return timeframe.atrsr.search_sorted_down(direction, price, depth, epsilon)
    else:
        return timeframe.atrsr.search_sorted_both(direction, price, depth, epsilon)


search_atrsr = search_std_atrsr
# search_atrsr = search_sorted_atrsr


def compute_take_profit(direction, data, entry_price, confidence=1.0, price_epsilon=0.0):
    timeframe = data.take_profit.timeframe

    def compute_distance():
        if direction > 0:
            # never larger than distance in percent if defined
            if data.stop_loss.distance_type == StrategyTraderContext.PRICE_FIXED_PCT:
                return entry_price * (1.0 + data.take_profit.distance)
            elif data.stop_loss.distance_type == StrategyTraderContext.PRICE_FIXED_DIST:
                return entry_price + data.take_profit.distance

        elif direction < 0:
            # never larger than distance in percent if defined
            if data.stop_loss.distance_type == StrategyTraderContext.PRICE_FIXED_PCT:
                return entry_price * (1.0 - data.take_profit.distance)
            elif data.stop_loss.distance_type == StrategyTraderContext.PRICE_FIXED_DIST:
                return entry_price - data.take_profit.distance

            return 0.0

    if direction > 0:
        min_dist = 1.0 + data.min_profit

        if data.take_profit.type == data.PRICE_NONE:
            return 0.0

        elif data.take_profit.type == data.PRICE_ATR_SR:
            atr_take_profit = search_atrsr(direction, data.take_profit.timeframe, data.take_profit.orientation,
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
            curatr_take_profit = data.take_profit.timeframe.atrsr._tup[-1] if len(data.take_profit.timeframe.atrsr._tup) else 0.0

            if data.take_profit.distance > 0.0:
                # never lesser than distance in percent if defined
                distance_take_profit = compute_distance()

                # if no current ATR return the fixed one, else return the higher
                if curatr_take_profit <= 0.0:
                    return distance_take_profit

                return max(curatr_take_profit, distance_take_profit)

            return curatr_take_profit

        elif data.take_profit.type == data.PRICE_HL2:
            lmin = entry_price
            lmax = timeframe.bollinger.tops[-1] if timeframe.bollinger and len(timeframe.bollinger.tops) else entry_price

            n = int(20 * confidence)

            for p in timeframe.price.high[-n:]:
                if not np.isnan(p) and p > entry_price:
                    lmax = max(lmax, p)
                    lmin = min(lmin, p)

            return max((lmin + lmax) * 0.5, entry_price * min_dist)

        elif data.take_profit.type == data.PRICE_ICHIMOKU:
            if not timeframe.ichimoku or not len(timeframe.ichimoku.ssas):
                return entry_price * min_dist

            n = 26
            lmin = 0

            for i in range(-n, 0):
                ssa = timeframe.ichimoku.ssas[i]
                ssb = timeframe.ichimoku.ssbs[i]
                v = 0

                if np.isnan(ssa) or np.isnan(ssb):
                    continue

                if ssa < ssb:
                    v = ssa
                else:
                    v = ssb

                if v > entry_price:
                    if not lmin:
                        lmin = v
                    else:
                        lmin = min(lmin, v)

            # at least 0.5%
            return max(lmin, entry_price * min_dist)

        elif data.take_profit.type == data.PRICE_BOLLINGER:
            if not timeframe.bollinger or not len(timeframe.bollinger.tops):
                return entry_price * min_dist

            tp = timeframe.bollinger.tops[-1]

            return max(tp, entry_price * min_dist)

        elif data.take_profit.type == data.PRICE_FIXED_PCT and data.take_profit.distance > 0.0:
            return entry_price * (1.0 + data.take_profit.distance)

        elif data.take_profit.type == data.PRICE_FIXED_DIST and data.take_profit.distance > 0.0:
            return entry_price + data.take_profit.distance

        elif data.stop_loss.type == data.PRICE_KIJUN:
            kijun_stop_loss = data.stop_loss.timeframe.ichimoku.kijuns[-1] if len(data.stop_loss.timeframe.ichimoku.kijuns) else 0.0

            if data.stop_loss.distance > 0.0:
                # never larger than distance in percent if defined
                distance_stop_loss = compute_distance()

                # if no current Kijun return the fixed one, else return the higher
                if kijun_stop_loss <= 0.0:
                    return distance_stop_loss

                return max(kijun_stop_loss, distance_stop_loss)

            return kijun_stop_loss

    elif direction < 0:
        min_dist = 1.0 - data.min_profit

        if data.take_profit.type == data.PRICE_NONE:
            return 0.0

        elif data.take_profit.type == data.PRICE_ATR_SR:
            atr_take_profit =  search_atrsr(direction, data.take_profit.timeframe, data.take_profit.orientation,
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
            curatr_take_profit =  data.take_profit.timeframe.atrsr._tdn[-1] if len(data.take_profit.timeframe.atrsr._tdn) else 0.0

            if data.take_profit.distance > 0.0:
                # never lesser than distance in percent if defined
                distance_take_profit = compute_distance()

                if curatr_take_profit <= 0.0:
                    # if no ATR found return the fixed one
                    return distance_take_profit

                return min(curatr_take_profit, distance_take_profit)

            return curatr_take_profit

        elif data.take_profit.type == data.PRICE_HL2:
            lmin = entry_price
            lmax = timeframe.bollinger.bottoms[-1] if timeframe.bollinger and len(timeframe.bollinger.bottoms) else entry_price

            n = int(20 * confidence)

            for p in timeframe.price.low[-n:]:
                if not np.isnan(p) and p < entry_price:
                    lmax = max(lmax, p)
                    lmin = min(lmin, p)

            return min((lmin + lmax) * 0.5, entry_price * min_dist)

        elif data.take_profit.type == data.PRICE_ICHIMOKU:
            if not timeframe.ichimoku or not len(timeframe.ichimoku.ssas):
                return entry_price * min_dist

            n = 26
            lmax = 0

            for i in range(-n, 0):
                ssa = timeframe.ichimoku.ssas[i]
                ssb = timeframe.ichimoku.ssbs[i]
                v = 0

                if np.isnan(ssa) or np.isnan(ssb):
                    continue

                if ssa > ssb:
                    v = ssa
                else:
                    v = ssb

                if v < entry_price:
                    if not lmax:
                        lmax = v
                    else:
                        lmax = max(lmax, v)

            # at least 0.5%
            return min(lmax, entry_price * min_dist)

        elif data.take_profit.type == data.PRICE_BOLLINGER:
            if not timeframe.bollinger or not len(timeframe.bollinger.bottoms):
                return entry_price * min_dist

            tp = timeframe.bollinger.bottoms[-1]

            return min(tp, entry_price * min_dist)

        elif data.take_profit.type == data.PRICE_FIXED_PCT and data.take_profit.distance > 0.0:
            return entry_price * (1.0 - data.take_profit.distance)

        elif data.take_profit.type == data.PRICE_FIXED_DIST and data.take_profit.distance > 0.0:
            return entry_price - data.take_profit.distance

        elif data.stop_loss.type == data.PRICE_KIJUN:
            kijun_stop_loss = data.stop_loss.timeframe.ichimoku.kijuns[-1] if len(data.stop_loss.timeframe.ichimoku.kijuns) else 0.0

            if data.stop_loss.distance > 0.0:
                # never larger than distance in percent if defined
                distance_stop_loss = compute_distance()

                if kijun_stop_loss <= 0.0:
                    # if no current Kijun return the fixed one
                    return distance_stop_loss

                return min(kijun_stop_loss, distance_stop_loss)

            return kijun_stop_loss

    return 0.0


def dynamic_take_profit_fixed_bollinger_long(timeframe, last_price, curr_take_profit_price, price_epsilon):
    take_profit = 0.0

    if timeframe.bollinger and len(timeframe.bollinger.tops) > 0:
        p = timeframe.bollinger.tops[-1]

        if p > curr_take_profit_price and p - price_epsilon > last_price:
            take_profit = p - price_epsilon

    return take_profit


def dynamic_take_profit_fixed_bollinger_short(timeframe, last_price, curr_take_profit_price, price_epsilon):
    take_profit = 0.0

    if timeframe.bollinger and len(timeframe.bollinger.bottoms) > 0:
        p = timeframe.bollinger.bottoms[-1]

        if p < curr_take_profit_price and p + price_epsilon < last_price:
            take_profit = p + price_epsilon

    return take_profit


def dynamic_take_profit_fixed_pct_long(timeframe, last_price, curr_take_profit_price, distance):
    take_profit = 0.0

    p = last_price * (1.0 + distance)

    if p > curr_take_profit_price and p > last_price:
        take_profit = p

    return take_profit


def dynamic_take_profit_fixed_pct_short(timeframe, last_price, curr_take_profit_price, distance):
    take_profit = 0.0

    p = last_price * (1.0 - distance)

    if p < curr_take_profit_price and p < last_price:
        take_profit = p

    return take_profit


def dynamic_take_profit_fixed_dist_long(timeframe, last_price, curr_take_profit_price, distance):
    take_profit = 0.0

    p = last_price + distance

    if p > curr_take_profit_price and p > last_price:
        take_profit = p

    return take_profit


def dynamic_take_profit_fixed_dist_short(timeframe, last_price, curr_take_profit_price, distance):
    take_profit = 0.0

    p = last_price - distance

    if p < curr_take_profit_price and p < last_price:
        take_profit = p

    return take_profit


def dynamic_take_profit_atrsr_long(timeframe, last_price, curr_take_profit_price, depth,
                                   orientation, price_epsilon=0.0):
    # search in short direction because be want a price lower than actual take-profit loss but we keep it
    # only if higher than current close price
    take_profit = search_atrsr(-1, timeframe, orientation, depth, curr_take_profit_price, price_epsilon)

    if take_profit > last_price + price_epsilon:
        return take_profit

    return 0.0

    # # or simply
    # take_profit = search_atrsr(1, timeframe, orientation, depth, curr_take_profit_price, price_epsilon)

    # if take_profit > last_price + price_epsilon and take_profit > curr_take_profit_price:
    #     return take_profit

    # return 0.0


def dynamic_take_profit_atrsr_short(timeframe, last_price, curr_take_profit_price, depth,
                                    orientation, price_epsilon=0.0):
    # reverse explanation of the long version (revert orientation)
    take_profit = search_atrsr(1, timeframe, -orientation, depth, curr_take_profit_price, price_epsilon)

    if take_profit < last_price - price_epsilon:
        return take_profit

    return 0.0

    # or simply (revert orientation)
    # take_profit = search_atrsr(-1, timeframe, -orientation, depth, curr_take_profit_price, price_epsilon)

    # if take_profit > last_price - price_epsilon and take_profit < curr_take_profit_price:
    #     return take_profit

    # return 0.0


def dynamic_take_profit_cur_atrsr_long(timeframe, entry_price, last_price, curr_take_profit_price, depth,
                                       orientation, price_epsilon=0.0):
    take_profit = 0.0

    if timeframe.atrsr and len(timeframe.atrsr._tup):
        if timeframe.atrsr._tup[-1] > curr_take_profit_price and timeframe.atrsr._tup[-1] > entry_price:
            take_profit = timeframe.atrsr._tup[-1]      

    if take_profit > last_price + price_epsilon:
        return take_profit

    return 0.0


def dynamic_take_profit_cur_atrsr_short(timeframe, entry_price, last_price, curr_take_profit_price, depth,
                                        orientation, price_epsilon=0.0):
    take_profit = 0.0

    if timeframe.atrsr and len(timeframe.atrsr._tdn):
        if timeframe.atrsr._tdn[-1] < curr_take_profit_price and timeframe.atrsr._tdn[-1] < entry_price:
            take_profit = timeframe.atrsr._tdn[-1]

    if take_profit < last_price - price_epsilon:
        return take_profit

    return 0.0


def dynamic_take_profit_volume_sr_long(timeframe, last_price, curr_take_profit_price):
    # @todo
    return 0.0


def dynamic_take_profit_volume_sr_short(timeframe, last_price, curr_take_profit_price):
    # @todo
    return 0.0


def dynamic_take_profit_kijun_long(timeframe, entry_price, last_price, curr_take_profit_price, price_epsilon=0.0):
    take_profit = 0.0

    if timeframe.ichimoku and timeframe.ichimoku.kijuns is not None and len(timeframe.ichimoku.kijuns) > 0:
        if 1:  # timeframe.last_closed:
            p = timeframe.ichimoku.kijuns[-1]

            # if p > last_price + price_epsilon:
            if curr_take_profit_price > p > last_price + price_epsilon:
                take_profit = p

    return take_profit


def dynamic_take_profit_kijun_short(timeframe, entry_price, last_price, curr_take_profit_price, price_epsilon=0.0):
    take_profit = 0.0

    if timeframe.ichimoku and timeframe.ichimoku.kijuns is not None and len(timeframe.ichimoku.kijuns) > 0:
        if 1:  # timeframe.last_closed:
            p = timeframe.ichimoku.kijuns[-1]

            # if p < last_price - price_epsilon:
            if curr_take_profit_price < p < last_price - price_epsilon:
                take_profit = p

    return take_profit


def dynamic_take_profit(direction, method, timeframe, entry_price, last_price, curr_take_profit_price, depth=1,
                        orientation=0, price_epsilon=0.0, distance=0.0):

    if direction > 0:
        if method == StrategyTraderContext.PRICE_NONE:
            return 0.0

        elif method == StrategyTraderContext.PRICE_ATR_SR:
            return dynamic_take_profit_atrsr_long(timeframe, last_price, curr_take_profit_price, depth,
                                                  orientation, price_epsilon)

        elif method == StrategyTraderContext.PRICE_CUR_ATR_SR:
            return dynamic_take_profit_cur_atrsr_long(timeframe, entry_price, last_price, curr_take_profit_price,
                                                      depth, orientation, price_epsilon)

        elif method == StrategyTraderContext.PRICE_BOLLINGER:
            return dynamic_take_profit_fixed_bollinger_long(timeframe, last_price, curr_take_profit_price,
                                                            price_epsilon)

        elif method == StrategyTraderContext.PRICE_FIXED_PCT and distance > 0.0:
            return dynamic_take_profit_fixed_pct_long(timeframe, last_price, curr_take_profit_price, distance)

        elif method == StrategyTraderContext.PRICE_FIXED_DIST and distance > 0.0:
            return dynamic_take_profit_fixed_dist_long(timeframe, last_price, curr_take_profit_price, distance)

        elif method == StrategyTraderContext.PRICE_VOL_SR:
            return dynamic_take_profit_volume_sr_long(timeframe, last_price, curr_take_profit_price)

        elif method == StrategyTraderContext.PRICE_KIJUN:
            return dynamic_take_profit_kijun_long(timeframe, last_price, curr_take_profit_price, price_epsilon)

    elif direction < 0:
        if method == StrategyTraderContext.PRICE_NONE:
            return 0.0

        elif method == StrategyTraderContext.PRICE_ATR_SR:
            return dynamic_take_profit_atrsr_short(timeframe, last_price, curr_take_profit_price, depth,
                                                   orientation, price_epsilon)

        elif method == StrategyTraderContext.PRICE_CUR_ATR_SR:
            return dynamic_take_profit_cur_atrsr_short(timeframe, entry_price, last_price, curr_take_profit_price,
                                                       depth, orientation, price_epsilon)

        elif method == StrategyTraderContext.PRICE_BOLLINGER:
            return dynamic_take_profit_fixed_bollinger_short(timeframe, last_price, curr_take_profit_price,
                                                             price_epsilon)

        elif method == StrategyTraderContext.PRICE_FIXED_PCT and distance > 0.0:
            return dynamic_take_profit_fixed_pct_short(timeframe, last_price, curr_take_profit_price, distance)

        elif method == StrategyTraderContext.PRICE_FIXED_DIST and distance > 0.0:
            return dynamic_take_profit_fixed_dist_short(timeframe, last_price, curr_take_profit_price, distance)

        elif method == StrategyTraderContext.PRICE_VOL_SR:
            return dynamic_take_profit_volume_sr_short(timeframe, last_price, curr_take_profit_price)

        elif method == StrategyTraderContext.PRICE_KIJUN:
            return dynamic_take_profit_kijun_short(timeframe, last_price, curr_take_profit_price, price_epsilon)

    return 0.0
