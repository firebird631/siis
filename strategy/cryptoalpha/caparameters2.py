# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Crypto Alpha strategy default parameters.

from instrument.instrument import Instrument

# magic 8,13,21,55,89,13
DEFAULT_PARAMS = {
    'reversal': True,
    'max-trades': 3,    # max number of simultaned trades for a same market
    'trade-delay': 30,  # at least wait 30 seconds before sending another signal 
    'base-timeframe': Instrument.TF_TICK,   # process each time strategy receive a tick
    'min-traded-timeframe': Instrument.TF_MIN,
    'max-traded-timeframe': Instrument.TF_MIN,
    'need-update': True,      # only compute when update is waited
    'min-vol24h': 100,        # 300 BTC per 24h
    'min-price': 0.00000069,  # or 69 sats (to binary otherwise)
    'region-allow': True,     # can trade if no defined region
    'timeframes': {
        # 'weekly': {
        #     'timeframe': Instrument.TF_WEEK,
        #     'parent': None,
        #     'mode': 'C',
        #     'depth': 22,
        #     'history': 22,
        #     'indicators': {
        #         'price': ('price', 1,),
        #         'volume': ('volume', 0,),
        #         'volume_ema': ('ema', 8,),
        #         'rsi': ('rsi', 14,),
        #         'stochrsi': ('stochrsi', 13, 13, 13),
        #         'sma': ('sma', 20,),
        #         'ema': ('ema', 21,),
        #         'hma': None,
        #         'vwma': ('vwma', 21,),
        #         'momentum': ('momentum', 21,),
        #         'stochastic': None,
        #         'macd': None,  # ('macd', 21,),
        #         'bollingerbands': ('bollingerbands', 36,),
        #         'triangle': None,
        #         'pivotpoint': ('pivotpoint', 5,),
        #         'tomdemark': None,
        #         'atr': ('atr', 14, 3.5),
        #         'bbawe': ('bbawe', 20, 2.0, 3.0, 5, 34, False),
        #     },
        #     'constants': {
        #         'rsi_low': 0.3,
        #         'rsi_high': 0.7,
        #     },
        # },
        # 'daily': {
        #     'timeframe': Instrument.TF_DAY,
        #     'parent': Instrument.TF_WEEK,
        #     'mode': 'B',
        #     'depth': 41,
        #     'history': 41,
        #     'indicators': {
        #         'price': ('price', 1,),
        #         'volume': ('volume', 0,),
        #         'volume_ema': ('ema', 8,),
        #         'rsi': ('rsi', 14,),
        #         'stochrsi': ('stochrsi', 13, 13, 13),
        #         'sma': ('sma', 20,),
        #         'ema': ('ema', 8,),
        #         'hma': None,
        #         'vwma': ('vwma', 21,),
        #         'momentum': ('momentum', 21,),
        #         'stochastic': None,
        #         'macd': None,  # ('macd', 21,),
        #         'bollingerbands': ('bollingerbands', 36,),
        #         'triangle': None,
        #         'pivotpoint': ('pivotpoint', 5,),
        #         'tomdemark': ('tomdemark', 9),
        #         'atr': ('atr', 14, 1.5),
        #         'bbawe': ('bbawe', 20, 2.0, 3.0, 5, 34, False),
        #     },
        #     'constants': {
        #         'rsi_low': 0.3,
        #         'rsi_high': 0.7,
        #     }
        # },
        '4hour': {
            'timeframe': Instrument.TF_4HOUR,
            'parent': None,  # Instrument.TF_DAY,
            'mode': 'B',
            'depth': 56,
            'history': 56,
            'indicators': {
                'price': ('price', 1,),
                'volume': ('volume', 0,),
                'volume_ema': ('ema', 8,),
                'rsi': ('rsi', 21,),
                'stochrsi': ('stochrsi', 13, 13, 13),
                #'sma200': ('sma', 200,),
                'sma55': ('sma', 55,),
                'sma': ('sma', 50,),
                'ema': ('ema', 20,),
                'hma': None,
                'vwma': ('vwma', 21,),
                'momentum': ('momentum', 21,),
                'stochastic': None,
                'macd': None,  # ('macd', 21,),
                'triangle': None,
                'pivotpoint': ('pivotpoint', 5,),
                'tomdemark': ('tomdemark', 9),
            },
            'constants': {
                'rsi_low': 0.3,
                'rsi_high': 0.7,
            }   
        },
        'hourly': {
            'timeframe': Instrument.TF_HOUR,
            'parent': Instrument.TF_4HOUR,
            'mode': 'B', 
            'depth': 22,
            'history': 22,
            'indicators': {
                'price': ('price', 1,),
                'volume': ('volume', 0,),
                'volume_ema': ('ema', 8,),
                'rsi': ('rsi', 14,),
                'stochrsi': ('stochrsi', 13, 13, 13),
                'sma200': None,
                'sma55': None,
                'sma': ('sma', 20,),
                'ema': ('ema', 8,),
                'hma': None,
                'vwma': ('vwma', 21,),
                'momentum': ('momentum', 21,),
                'stochastic': None,
                'macd': None,  # ('macd', 21,),
                'bollingerbands': ('bollingerbands', 36,),
                'triangle': None,
                'pivotpoint': ('pivotpoint', 5,),
                'tomdemark': ('tomdemark', 9),
                'atr': ('atr', 14, 2.0),
            },
            'constants': {
                'rsi_low': 0.3,
                'rsi_high': 0.7,
            }
        },
        '30min': {
            'timeframe': Instrument.TF_30MIN,
            'parent': Instrument.TF_HOUR,
            'mode': 'B',
            'depth': 22,
            'history': 22,
            'indicators': {
                'price': ('price', 1,),
                'volume': ('volume', 0,),
                'volume_ema': ('ema', 8,),
                'rsi': ('rsi', 14,),
                'sma': ('sma', 20,),
                'ema': ('ema', 8,),
                'hma': None,
                'vwma': ('vwma', 21,),
                'momentum': ('momentum', 21,),
                'stochastic': None,
                'macd': None,  # ('macd', 21,),
                'bollingerbands': ('bollingerbands', 36,),
                'triangle': None,
                'pivotpoint': ('pivotpoint', 0,),
                'tomdemark': ('tomdemark', 9),
                'atr': ('atr', 14, 2.0),
            },
            'constants': {
                'rsi_low': 0.3,
                'rsi_high': 0.7,
            }
        },
        '1min': {
            'timeframe': Instrument.TF_MIN,
            'parent': Instrument.TF_30MIN,
            'mode': 'A',
            'depth': 36,
            'history': 36,
            'indicators': {
                'price': ('price', 1,),
                'volume': ('volume', 0,),
                'rsi': ('rsi', 14,),
                'stochrsi': ('stochrsi', 13, 13, 13),
                'sma': ('sma', 20,),
                'ema': ('ema', 8,),
                'hma': ('hma', 8,),
                'vwma': ('vwma', 8,),
                'momentum': ('momentum', 20,),
                'stochastic': None,
                'macd': None,  # ('macd', 17,),
                'bollingerbands': None, # ('bollingerbands', 26,),
                'triangle': None,
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
