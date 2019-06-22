# @date 2019-01-19
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Crystal ball strategy indicator default parameters.

from instrument.instrument import Instrument

DEFAULT_PARAMS = {
    'reversal': True,
    'pyramided': 0,
    'hedging': False,
    'max-trades': 3,    # max number of simultaned trades for a same market
    'trade-delay': 30,  # at least wait 30 seconds before sending another signal 
    'base-timeframe': Instrument.TF_TICK,   # process each time strategy receive a tick
    'min-traded-timeframe': Instrument.TF_MIN,
    'max-traded-timeframe': Instrument.TF_4HOUR,
    'need-update': False,     # only compute when update is waited
    'min-vol24h': 100,        # 300 BTC per 24h
    'min-price': 0.00000069,  # or 69 sats (to binary otherwise)
    'timeframes': [
        {
            'timeframe': Instrument.TF_4HOUR,
            'parent':None,
            'mode': 'A',
            'depth': 22,
            'history': 22,
            'indicators': {
                'price': ('price', 2,),
                'volume': ('volume', 0,),
                'rsi': ('rsi', 21,),
                'pivotpoint': ('pivotpoint', 5,),
                'tomdemark': ('tomdemark', 9),
                'atr': ('atr', 14, 1.0),  # was 1.5 , but too large else
                'bbawe': ('bbawe', 20, 2.0, 3.0, 5, 34, False),
            },
            'constants': {
                'rsi_low': 0.3,
                'rsi_high': 0.7,
            }   
        },
        {
            'timeframe': Instrument.TF_HOUR,
            'parent': Instrument.TF_4HOUR,
            'mode': 'A', 
            'depth': 22,
            'history': 22,
            'indicators': {
                'price': ('price', 2,),
                'volume': ('volume', 0,),
                'rsi': ('rsi', 21,),
                'pivotpoint': ('pivotpoint', 5,),
                'tomdemark': ('tomdemark', 9),
                'atr': ('atr', 14, 1.0),  # was 1.5 , but too large else
                'bbawe': ('bbawe', 20, 2.0, 3.0, 5, 34, False),
            },
            'constants': {
                'rsi_low': 0.3,
                'rsi_high': 0.7,
            }
        },
        {
            'timeframe': Instrument.TF_15MIN,
            'parent': Instrument.TF_HOUR,
            'mode': 'A',
            'depth': 22,
            'history': 22,
            'indicators': {
                'price': ('price', 2,),
                'volume': ('volume', 0,),
                'rsi': ('rsi', 21,),
                'pivotpoint': ('pivotpoint', 5,),
                'tomdemark': ('tomdemark', 9),
                'atr': ('atr', 14, 1.0),
                'bbawe': ('bbawe', 20, 2.0, 3.0, 5, 34, False),
            },
            'constants': {
                'rsi_low': 0.3,
                'rsi_high': 0.7,
            }
        },
        {
            'timeframe': Instrument.TF_5MIN,
            'parent': Instrument.TF_15MIN,
            'mode': 'A',
            'depth': 22,
            'history': 22,
            'indicators': {
                'price': ('price', 2,),
                'volume': ('volume', 0,),
                'rsi': ('rsi', 21,),
                'pivotpoint': ('pivotpoint', 5,),
                'tomdemark': ('tomdemark', 9),
                'atr': ('atr', 14, 3.0),
                'bbawe': ('bbawe', 20, 2.0, 3.0, 5, 34, False),
            },
            'constants': {
                'rsi_low': 0.3,
                'rsi_high': 0.7,
            }
        },
        {
            'timeframe': Instrument.TF_2MIN,
            'parent': Instrument.TF_5MIN,
            'mode': 'A',
            'depth': 22,
            'history': 22,
            'indicators': {
                'price': ('price', 2,),
                'volume': ('volume', 0,),
                'rsi': ('rsi', 21,),
                'pivotpoint': ('pivotpoint', 5,),
                'tomdemark': ('tomdemark', 9),
                'atr': ('atr', 14, 3.0),
                'bbawe': ('bbawe', 20, 2.0, 3.0, 5, 34, False),
            },
            'constants': {
                'rsi_low': 0.3,
                'rsi_high': 0.7,
            }
        },
        {
            'timeframe': Instrument.TF_MIN,
            'parent': Instrument.TF_2MIN,
            'mode': 'A',
            'depth': 22,
            'history': 22,
            'indicators': {
                'price': ('price', 2,),
                'volume': ('volume', 0,),
                'rsi': ('rsi', 21,),
                'pivotpoint': ('pivotpoint', 5,),
                'tomdemark': ('tomdemark', 9),
                'atr': ('atr', 14, 3.0),
                'bbawe': ('bbawe', 20, 2.0, 3.0, 5, 34, False),
            },
            'constants': {
                'rsi_low': 0.3,
                'rsi_high': 0.7,
            }
        }
    ]
}
