# @date 2019-01-19
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Crystal ball strategy indicator default parameters.

DEFAULT_PARAMS = {
    'reversal': True,
    'pyramided': 0,
    'hedging': False,
    'max-trades': 3,    # max number of simultaned trades for a same market
    'trade-delay': 30,  # at least wait 30 seconds before sending another signal 
    'base-timeframe': 't',   # process each time strategy receive a tick
    'min-traded-timeframe': '1m',
    'max-traded-timeframe': '4h',
    'need-update': False,     # only compute when update is waited
    'min-vol24h': 100,        # 300 BTC per 24h
    'min-price': 0.00000069,  # or 69 sats (to binary otherwise)
    'timeframes': {
        '4hour': {
            'timeframe': '4h',
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
        'hourly': {
            'timeframe': '1h',
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
        '15min': {
            'timeframe': '15m',
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
        '5min': {
            'timeframe': '5m',
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
        '2min':{
            'timeframe': '2m',
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
        '1min': {
            'timeframe': '1m',
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
    }
}
