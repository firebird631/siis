# @date 2019-09-12
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Base strategy stop loss methods

import numpy as np

from strategy.strategysignalcontext import BaseSignal


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


def compute_stop_loss(direction, data, entry_price, confidence=1.0, price_epsilon=0.0):
    """
    Branching to the predefined stop-loss method.
    """
    timeframe = data.stop_loss.timeframe

    if direction > 0:
        min_dist = 1.0 - data.min_profit

        if data.stop_loss.type == data.PRICE_NONE:
            return 0.0

        elif data.stop_loss.type == data.PRICE_ATR_SR:
            atr_stop_loss = search_atrsr(-direction, data.stop_loss.timeframe, data.stop_loss.orientation, data.stop_loss.depth, entry_price, price_epsilon)

            if data.stop_loss.distance > 0.0:
                # never larger than distance in percent if defined
                fixed_pct_stop_loss = entry_price * (1.0 - data.stop_loss.distance)

                # if no ATR found return the fixed one, else return the higher
                if atr_stop_loss <= 0.0:
                    return fixed_pct_stop_loss

                return max(atr_stop_loss, fixed_pct_stop_loss)

            return atr_stop_loss

        elif data.stop_loss.type == data.PRICE_CUR_ATR_SR:
            curatr_stop_loss = data.stop_loss.timeframe.atrsr._tdn[-1] if len(data.stop_loss.timeframe.atrsr._tdn) else 0.0

            if data.stop_loss.distance > 0.0:
                # never larger than distance in percent if defined
                fixed_pct_stop_loss = entry_price * (1.0 - data.stop_loss.distance)

                # if no current ATR return the fixed one, else return the higher
                if curatr_stop_loss <= 0.0:
                    return fixed_pct_stop_loss

                return max(curatr_stop_loss, fixed_pct_stop_loss)

            return curatr_stop_loss

        elif data.stop_loss.type == data.PRICE_BOLLINGER:
            lmin = entry_price
            lmax = 0.0

            n = int(20 * confidence)

            for p in timeframe.bollinger.bottoms[-n:]:
                if not np.isnan(p) and p > 0.0 and p < entry_price:
                    lmax = max(lmax, p)
                    lmin = min(lmin, p)

            #return min((lmax + lmin) * 0.5, entry_price * (1.0 - data.stop_loss.distance))
            return min((entry_price + lmin) * 0.5, entry_price * min_dist)

        elif data.stop_loss.type == data.PRICE_FIXED_PCT and data.stop_loss.distance > 0.0:
            return entry_price * (1.0 - data.stop_loss.distance)

        elif data.stop_loss.type == data.PRICE_FIXED_DIST and data.stop_loss.distance > 0.0:
            return entry_price - data.stop_loss.distance

    elif direction < 0:
        min_dist = 1.0 + data.min_profit

        if data.stop_loss.type == data.PRICE_NONE:
            return 0.0

        elif data.stop_loss.type == data.PRICE_ATR_SR:
            atr_stop_loss = search_atrsr(-direction, data.stop_loss.timeframe, data.stop_loss.orientation, data.stop_loss.depth, entry_price, price_epsilon)

            if data.stop_loss.distance > 0.0:
                # never larger than distance in percent if defined
                fixed_pct_stop_loss = entry_price * (1.0 + data.stop_loss.distance)

                if atr_stop_loss <= 0.0:
                    # if no ATR found return the fixed one
                    return fixed_pct_stop_loss

                return min(atr_stop_loss, fixed_pct_stop_loss)

            return atr_stop_loss

        elif data.stop_loss.type == data.PRICE_CUR_ATR_SR:
            curatr_stop_loss = data.stop_loss.timeframe.atrsr._tup[-1] if len(data.stop_loss.timeframe.atrsr._tup) else 0.0

            if data.stop_loss.distance > 0.0:
                # never larger than distance in percent if defined
                fixed_pct_stop_loss = entry_price * (1.0 + data.stop_loss.distance)

                if curatr_stop_loss <= 0.0:
                    # if no current ATR return the fixed one
                    return fixed_pct_stop_loss

                return min(curatr_stop_loss, fixed_pct_stop_loss)

            return curatr_stop_loss

        elif data.stop_loss.type == data.PRICE_BOLLINGER:
            lmin = entry_price
            lmax = 0.0

            n = int(20 * confidence)

            for p in timeframe.bollinger.tops[-n:]:
                if not np.isnan(p) and p > 0.0 and p > entry_price:
                    lmax = max(lmax, p)
                    lmin = min(lmin, p)

            return max((lmax - entry_price) * 0.5, entry_price * min_dist)

        elif data.stop_loss.type == data.PRICE_FIXED_PCT and data.stop_loss.distance > 0.0:
            return entry_price * (1.0 + data.stop_loss.distance)

        elif data.stop_loss.type == data.PRICE_FIXED_DIST and data.stop_loss.distance > 0.0:
            return entry_price + data.stop_loss.distance

    return 0.0


def dynamic_stop_loss_fixed_bollinger_long(timeframe, last_price, curr_stop_loss_price, price_epsilon=0.0):
    stop_loss = 0.0

    if timeframe.bollinger and timeframe.bollinger.bottoms is not None and len(timeframe.bollinger.bottoms) > 0:
        if 1:  # timeframe.last_closed:
            p = timeframe.bollinger.bottoms[-1]

            if p > curr_stop_loss_price and p < last_price - price_epsilon:
                stop_loss = p

    return stop_loss


def dynamic_stop_loss_fixed_bollinger_short(timeframe, last_price, curr_stop_loss_price, price_epsilon=0.0):
    stop_loss = 0.0

    if timeframe.bollinger and timeframe.bollinger.tops is not None and len(timeframe.bollinger.tops) > 0:
        if 1:  # timeframe.last_closed:
            p = timeframe.bollinger.tops[-1]

            if p < curr_stop_loss_price and p > last_price + price_epsilon:
                stop_loss = p

    return stop_loss


def dynamic_stop_loss_fixed_pct_long(timeframe, last_price, curr_stop_loss_price, distance):
    stop_loss = 0.0

    p = last_price * (1.0 - distance)

    if p > curr_stop_loss_price and p < last_price:
        stop_loss = p

    return stop_loss


def dynamic_stop_loss_fixed_pct_short(timeframe, last_price, curr_stop_loss_price, distance):
    stop_loss = 0.0

    p = last_price * (1.0 + distance)

    if p < curr_stop_loss_price and p > last_price:
        stop_loss = p

    return stop_loss


def dynamic_stop_loss_fixed_dist_long(timeframe, last_price, curr_stop_loss_price, distance):
    stop_loss = 0.0

    p = last_price - distance

    if p > curr_stop_loss_price and p < last_price:
        stop_loss = p

    return stop_loss


def dynamic_stop_loss_fixed_dist_short(timeframe, last_price, curr_stop_loss_price, distance):
    stop_loss = 0.0

    p = last_price + distance

    if p < curr_stop_loss_price and p > last_price:
        stop_loss = p

    return stop_loss


def dynamic_stop_loss_atrsr_long(timeframe, last_price, curr_stop_loss_price, depth, orientation, price_epsilon=0.0):
    # search in long direction because be want a price greater than actual stop loss but we keep it only
    # if lesser than current close price
    # stop_loss = search_atrsr(1, timeframe, orientation, depth, curr_stop_loss_price, price_epsilon)

    # if stop_loss < last_price - price_epsilon:
    #     return stop_loss

    # return 0.0

    # or simply
    stop_loss = search_atrsr(-1, timeframe, orientation, depth, last_price, 0)  # price_epsilon)

    if stop_loss < last_price - price_epsilon and stop_loss > curr_stop_loss_price:
        return stop_loss

    return 0.0


def dynamic_stop_loss_atrsr_short(timeframe, last_price, curr_stop_loss_price, depth, orientation, price_epsilon=0.0):
    # reverse explanation of the long version
    # stop_loss = search_atrsr(-1, timeframe, -orientation, depth, curr_stop_loss_price, price_epsilon)

    # if stop_loss > last_price + price_epsilon:
    #     return stop_loss

    # return 0.0

    # or simply (revert orientation)
    stop_loss = search_atrsr(1, timeframe, -orientation, depth, last_price, 0)  # price_epsilon)

    if stop_loss > last_price + price_epsilon and stop_loss < curr_stop_loss_price:
        return stop_loss

    return 0.0


def dynamic_stop_loss_cur_atrsr_long(timeframe, entry_price, last_price, curr_stop_loss_price, depth, orientation, price_epsilon=0.0):
    stop_loss = 0.0

    if timeframe.atrsr and len(timeframe.atrsr._tdn):
        if timeframe.atrsr._tdn[-1] > curr_stop_loss_price and timeframe.atrsr._tdn[-1] < last_price:
            stop_loss = timeframe.atrsr._tdn[-1]

    # if timeframe.atrsr and len(timeframe.atrsr._tup):
    #     if timeframe.atrsr._tup[-1] > curr_stop_loss_price and timeframe.atrsr._tup[-1] < last_price:
    #         stop_loss = timeframe.atrsr._tup[-1]

    # if stop_loss < last_price:
    #     return stop_loss - price_epsilon

    if stop_loss < last_price - price_epsilon:
        return stop_loss - price_epsilon

    return 0.0


def dynamic_stop_loss_cur_atrsr_short(timeframe, entry_price, last_price, curr_stop_loss_price, depth, orientation, price_epsilon=0.0):
    stop_loss = 0.0

    if timeframe.atrsr and len(timeframe.atrsr._tup):
        if timeframe.atrsr._tup[-1] < curr_stop_loss_price and timeframe.atrsr._tup[-1] > last_price:
            stop_loss = timeframe.atrsr._tup[-1]

    # if timeframe.atrsr and len(timeframe.atrsr._tdn):
    #     if timeframe.atrsr._tdn[-1] < curr_stop_loss_price and timeframe.atrsr._tdn[-1] > last_price:
    #         stop_loss = timeframe.atrsr._tdn[-1]

    # if stop_loss > last_price:
    #     return stop_loss + price_epsilon

    if stop_loss > last_price + price_epsilon:
        return stop_loss + price_epsilon

    return 0.0


def dynamic_stop_loss_fixed_hma_long(timeframe, last_price, curr_stop_loss_price, price_epsilon=0.0):
    stop_loss = 0.0

    if timeframe.hma and timeframe.hma.hmas is not None and len(timeframe.hma.hmas) > 0:
        if 1:  # timeframe.last_closed:
            p = timeframe.hma.hmas[-1]

            if p > curr_stop_loss_price and p < last_price - price_epsilon:
                stop_loss = p

    return stop_loss


def dynamic_stop_loss_fixed_hma_short(timeframe, last_price, curr_stop_loss_price, price_epsilon=0.0):
    stop_loss = 0.0

    if timeframe.hma and timeframe.hma.hmas is not None and len(timeframe.hma.hmas) > 0:
        if 1:  # timeframe.last_closed:
            p = timeframe.hma.hmas[-1]

            if p < curr_stop_loss_price and p > last_price + price_epsilon:
                stop_loss = p

    return stop_loss


def dynamic_stop_loss_volume_sr_long(timeframe, last_price, curr_stop_loss_price):
    # @todo
    return 0.0


def dynamic_stop_loss_volume_sr_short(timeframe, last_price, curr_stop_loss_price):
    # @todo
    return 0.0


def dynamic_stop_loss(direction, method, timeframe, entry_price, last_price, curr_stop_loss_price, depth=1,
                      orientation=0, price_epsilon=0.0, distance=0.0):
    if direction > 0:
        if method == BaseSignal.PRICE_NONE:
            return 0.0

        elif method == BaseSignal.PRICE_ATR_SR:
            return dynamic_stop_loss_atrsr_long(timeframe, last_price, curr_stop_loss_price, depth, orientation,
                                                price_epsilon)

        elif method == BaseSignal.PRICE_CUR_ATR_SR:
            return dynamic_stop_loss_cur_atrsr_long(timeframe, entry_price, last_price, curr_stop_loss_price, depth,
                                                    orientation, price_epsilon)

        elif method == BaseSignal.PRICE_BOLLINGER:
            return dynamic_stop_loss_fixed_bollinger_long(timeframe, last_price, curr_stop_loss_price, price_epsilon)

        elif method == BaseSignal.PRICE_FIXED_PCT and distance > 0.0:
            return dynamic_stop_loss_fixed_pct_long(timeframe, last_price, curr_stop_loss_price, distance)

        elif method == BaseSignal.PRICE_HMA:
            return dynamic_stop_loss_fixed_dist_long(timeframe, last_price, curr_stop_loss_price, distance)

        elif method == BaseSignal.PRICE_HMA and distance > 0.0:
            return dynamic_stop_loss_fixed_hma_long(timeframe, last_price, curr_stop_loss_price, price_epsilon)

        elif method == BaseSignal.PRICE_VOL_SR:
            return dynamic_stop_loss_volume_sr_long(timeframe, last_price, curr_stop_loss_price)

    elif direction < 0:
        if method == BaseSignal.PRICE_NONE:
            return 0.0

        elif method == BaseSignal.PRICE_ATR_SR:
            return dynamic_stop_loss_atrsr_short(timeframe, last_price, curr_stop_loss_price, depth, orientation,
                                                 price_epsilon)

        elif method == BaseSignal.PRICE_CUR_ATR_SR:
            return dynamic_stop_loss_cur_atrsr_short(timeframe, entry_price, last_price, curr_stop_loss_price, depth,
                                                     orientation, price_epsilon)

        elif method == BaseSignal.PRICE_BOLLINGER:
            return dynamic_stop_loss_fixed_bollinger_short(timeframe, last_price, curr_stop_loss_price, price_epsilon)

        elif method == BaseSignal.PRICE_FIXED_PCT and distance > 0.0:
            return dynamic_stop_loss_fixed_pct_short(timeframe, last_price, curr_stop_loss_price, distance)

        elif method == BaseSignal.PRICE_FIXED_DIST and distance > 0.0:
            return dynamic_stop_loss_fixed_dist_short(timeframe, last_price, curr_stop_loss_price, distance)

        elif method == BaseSignal.PRICE_HMA:
            return dynamic_stop_loss_fixed_hma_short(timeframe, last_price, curr_stop_loss_price, price_epsilon)

        elif method == BaseSignal.PRICE_VOL_SR:
            return dynamic_stop_loss_volume_sr_short(timeframe, last_price, curr_stop_loss_price)

    return 0.0
