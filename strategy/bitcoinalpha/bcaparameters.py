# @date 2019-01-19
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Bitcoin Alpha strategy default parameters.

from instrument.instrument import Instrument

DEFAULT_PARAMS = {
    'reversal': True,
    'pyramided': 0,
    'hedging': False,
    'max-trades': 3,    # max number of simultaned trades for a same market
    'trade-delay': 30,  # at least wait 30 seconds before sending another signal 
    'base-timeframe': Instrument.TF_TICK,   # process each time strategy receive a tick
    'min-traded-timeframe': Instrument.TF_2MIN,
    'max-traded-timeframe': Instrument.TF_15MIN,
    'need-update': False,      # only compute when update is waited
    'min-vol24h': 100,        # 300 BTC per 24h
    'min-price': 0.00000069,  # or 69 sats (to binary otherwise)
    'timeframes': [
        {
            'timeframe': Instrument.TF_DAY,
            'parent': None,
            'mode': 'A',
            'depth': 41,
            'history': 41,
            'indicators': {
                'price': ('price', 1,),
                'volume': ('volume', 0,),
                'volume_ema': ('ema', 8,),
                'rsi': ('rsi', 21,),
                'stochrsi': ('stochrsi', 13, 13, 13),
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
                'atr': ('atr', 14, 1.5),
                'bbawe': ('bbawe', 20, 2.0, 3.0, 5, 34, False),
            },
            'constants': {
                'rsi_low': 0.3,
                'rsi_high': 0.7,
            }
        },
        {
            'timeframe': Instrument.TF_4HOUR,
            'parent': Instrument.TF_DAY,
            'mode': 'A',
            'depth': 56,
            'history': 56,
            'indicators': {
                'price': ('price', 1,),
                'volume': ('volume', 0,),
                'volume_ema': ('ema', 8,),
                'rsi': ('rsi', 21,),
                'stochrsi': ('stochrsi', 13, 13, 13),
                'sma200': ('sma', 200,),
                'sma55': ('sma', 55,),
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
                'atr': ('atr', 14, 0.5),  # was 1.5 , but too large else
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
            'depth': 41,
            'history': 41,
            'indicators': {
                'price': ('price', 1,),
                'volume': ('volume', 0,),
                'volume_ema': ('ema', 8,),
                'rsi': ('rsi', 21,),
                'stochrsi': ('stochrsi', 13, 13, 13),
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
                'atr': ('atr', 14, 0.5),  # was 1.5 , but too large else
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
            'depth': 41,
            'history': 41,
            'indicators': {
                'price': ('price', 1,),
                'volume': ('volume', 0,),
                'volume_ema': ('ema', 8,),
                'rsi': ('rsi', 21,),
                'stochrsi': ('stochrsi', 13, 13, 13),
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
                'atr': ('atr', 21, 0.5),
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
            'depth': 41,
            'history': 41,
            'indicators': {
                'price': ('price', 1,),
                'volume': ('volume', 0,),
                'volume_ema': ('ema', 8,),
                'rsi': ('rsi', 21,),
                'stochrsi': ('stochrsi', 13, 13, 13),
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
                'atr': ('atr', 40, 1.5),
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
            'depth': 41,
            'history': 41,
            'indicators': {
                'price': ('price', 1,),
                'volume': ('volume', 0,),
                'rsi': ('rsi', 21,),
                'stochrsi': ('stochrsi', 13, 13, 13),
                'sma': ('sma', 20,),
                'ema': ('ema', 8,),
                'hma': ('hma', 8,),
                'vwma': ('vwma', 8,),
                'momentum': ('momentum', 20,),
                'stochastic': None,
                'macd': None,  # ('macd', 17,),
                'bollingerbands': ('bollingerbands', 36,),
                'triangle': None,
                'pivotpoint': ('pivotpoint', 5,),
                'tomdemark': ('tomdemark', 9),
                'atr': ('atr', 40, 2.0),
                'bbawe': ('bbawe', 20, 2.0, 3.0, 5, 34, False),
            },
            'constants': {
                'rsi_low': 0.3,
                'rsi_high': 0.7,
            }
        }
    ]
}


# # magic 8,13,21,55,89,13
# DEFAULT_PARAMS = {
#     'reversal': True,
# 	'pyramided': 0,
#     'max-trades': 3,    # max number of simultaned trades for a same market
#     'trade-delay': 30,  # at least wait 30 seconds before sending another signal 
#     'score-trigger': 0.5,
#     'score-increase-factor': 0.4,
#     'score-regression-factor': 0.3,
#     'base-timeframe': Instrument.TF_TICK,   # process each time strategy receive a tick
#     'min-traded-timeframe': Instrument.TF_MIN,
#     'max-traded-timeframe': Instrument.TF_HOUR,
#     'need-update': False,     # only compute when update is waited
#     'min-vol24h': 100,        # 300 BTC per 24h
#     'min-price': 0.00000069,  # or 69 sats (to binary otherwise)
#     'timeframes': [
#         {
#             'timeframe': Instrument.TF_WEEK,
#             'sub-tf': Instrument.TF_DAY,
#             'mode': 'C',
#             'depth': 22,
#             'history': 22,  #52,  # 1 year
#             'score-ratio': 8,
#             'score-level': 0.05,
#             'indicators': {
#                 'price': (1,),
#                 'volume': (0,),
#                 'rsi': (21,),
#                 'stochrsi': (13, 13, 13),
#                 'sma': (21,),
#                 'ema': (21,),
#                 'hma': None,
#                 'vwma': (21,),
#                 'momentum': (21,),
#                 'stochastic': None,
#                 'macd': None,  # (21,),
#                 'bollingerbands': (21,),
#                 'triangle': None,
#                 'fibonacci': None,  # (15,),
#                 'pivotpoint': None, # (1,),
#                 'tomdemark': None,
#                 'atr': (20, 3),
#             },
#             'constants': {
#                 'rsi_low': 0.3,
#                 'rsi_high': 0.7,
#             },
#             'scores': {
#                 'rsi_factor': 1.0,
#                 'rsi_trend_factor': 0.5,
#                 'sma_ema_cross_factor': (-0.5, -0.5),  # no-div/div
#                 'ema_vwma_cross_factor': (-5, -5),
#                 'price_vwma_factor': 50.0,
#                 'ema_vwma_cross_bonus': 0,  # 1,2,3,5
#                 'rsi_ema_trend_div_factor': (-0.04, -0.04),
#             },
#         },
#         {
#             'timeframe': Instrument.TF_DAY,
#             'sub-tf': Instrument.TF_4HOUR,
#             'mode': 'C',
#             'depth': 22,
#             'history': 22,  #365,  # 365 days
#             'score-ratio': 8,
#             'score-level': 0.05,
#             'indicators': {
#                 'price': (1,),
#                 'volume': (0,),
#                 'rsi': (21,),
#                 'stochrsi': (13, 13, 13),
#                 'sma': (20,),
#                 'ema': (20,),
#                 'hma': None,
#                 'vwma': (20,),
#                 'momentum': (20,),
#                 'stochastic': None,
#                 'macd': None,  # (21,),
#                 'bollingerbands': (21,),
#                 'triangle': None,
#                 'fibonacci': None,  # (15,),
#                 'pivotpoint': None, # (1,),
#                 'tomdemark': None,
#                 'atr': (20, 3),
#             },
#             'constants': {
#                 'rsi_low': 0.3,
#                 'rsi_high': 0.7,
#             },
#             'scores': {
#                 'rsi_factor': 1.0,
#                 'rsi_trend_factor': 0.5,
#                 'sma_ema_cross_factor': (-0.5, -0.5),  # no-div/div
#                 'ema_vwma_cross_factor': (-5, -5),
#                 'price_vwma_factor': 50.0,
#                 'ema_vwma_cross_bonus': 0,  # 1,2,3,5
#                 'rsi_ema_trend_div_factor': (-0.04, -0.04),
#             },
#         },
#         {
#             'timeframe': Instrument.TF_4HOUR,
#             'sub-tf': Instrument.TF_HOUR,
#             'mode': 'A',
#             'depth': 55,
#             'history': 55,  # 252,  # 42 days
#             'score-ratio': 6,
#             'score-level': 0.05,
#             'indicators': {
#                 'price': (1,),
#                 'volume': (0,),
#                 'rsi': (21,),
#                 'stochrsi': (13, 13, 13),
#                 'sma': (21,),
#                 'ema': (55,),
#                 'hma': None,
#                 'vwma': (21,),
#                 'momentum': (21,),
#                 'stochastic': None,
#                 'macd': None,  # (17,),
#                 'bollingerbands': (21,),
#                 'triangle': None,
#                 'fibonacci': None,  # (15,),
#                 'pivotpoint': None, # (1,),
#                 'tomdemark': (9,),
#                 'atr': (20, 3),
#             },
#             'constants': {
#                 'rsi_low': 0.3,
#                 'rsi_high': 0.7,
#             },
#             'scores': {
#                 'rsi_factor': 1.0,
#                 'rsi_trend_factor': 0.5,
#                 'sma_ema_cross_factor': (-0.5, -0.5),  # no-div/div
#                 'ema_vwma_cross_factor': (-5, -5),
#                 'price_vwma_factor': 50.0,
#                 'ema_vwma_cross_bonus': 0,  # 1,2,3,5
#                 'rsi_ema_trend_div_factor': (-0.04, -0.04),
#             }   
#         },
#         {
#             'timeframe': Instrument.TF_HOUR,
#             'sub-tf': Instrument.TF_15MIN,
#             'mode': 'A',
#             'depth': 22,
#             'history': 22, # 504,  # 21 days
#             'score-ratio': 4,
#             'score-level': 0.05,
#             'indicators': {
#                 'price': (1,),
#                 'volume': (0,),
#                 'rsi': (21,),
#                 'stochrsi': (13, 13, 13),
#                 'sma': (21,),
#                 'ema': (21,),
#                 'hma': None,
#                 'vwma': (21,),
#                 'momentum': (21,),
#                 'stochastic': None,
#                 'macd': None,  # (17,),
#                 'bollingerbands': (21,),
#                 'triangle': None,
#                 'fibonacci': None,  # (15,),
#                 'pivotpoint': None, #(1,),
#                 'tomdemark': (9,),
#                 'atr': (20, 3),
#             },
#             'constants': {
#                 'rsi_low': 0.3,
#                 'rsi_high': 0.7,
#             },
#             'scores': {
#                 'rsi_factor': 1.0,
#                 'rsi_trend_factor': 0.5,
#                 'sma_ema_cross_factor': (-0.5, -0.5),  # no-div/div
#                 'ema_vwma_cross_factor': (-5, -5),
#                 'price_vwma_factor': 50.0,
#                 'ema_vwma_cross_bonus': 0,  # 1,2,3,5
#                 'rsi_ema_trend_div_factor': (-0.04, -0.04),
#             }
#         },
#         {
#             'timeframe': Instrument.TF_15MIN,
#             'sub-tf': Instrument.TF_5MIN,
#             'mode': 'A',
#             'depth': 22,
#             'history': 22,  #504,  # 5.25 days
#             'score-ratio': 2,
#             'score-level': 0.05,
#             'indicators': {
#                 'price': (1,),
#                 'volume': (0,),
#                 'rsi': (21,),
#                 'stochrsi': (13, 13, 13),
#                 'sma': (21,),
#                 'ema': (21,),
#                 'hma': None,
#                 'vwma': (21,),
#                 'momentum': (21,),
#                 'stochastic': None,
#                 'macd': None,  # (17,),
#                 'bollingerbands': (21,),
#                 'triangle': None,
#                 'fibonacci': None,  # (15,),
#                 'pivotpoint': None, #(1,),
#                 'tomdemark': (9,),
#                 'atr': (20, 3),
#             },
#             'constants': {
#                 'rsi_low': 0.3,
#                 'rsi_high': 0.7,
#             },
#             'scores': {
#                 'rsi_factor': 1.0,
#                 'rsi_trend_factor': 0.5,
#                 'sma_ema_cross_factor': (-0.5, -0.5),  # no-div/div
#                 'ema_vwma_cross_factor': (-5, -5),
#                 'price_vwma_factor': 50.0,
#                 'ema_vwma_cross_bonus': 0,  # 1,2,3,5
#                 'rsi_ema_trend_div_factor': (-0.04, -0.04),
#             }
#         },
#         {
#             'timeframe': Instrument.TF_5MIN,
#             'sub-tf': Instrument.TF_MIN,
#             'mode': 'A',
#             'depth': 14,
#             'history': 14, # 1152,  # 4 days
#             'score-ratio': 1,
#             'score-level': 0.05,
#             'indicators': {
#                 'price': (1,),
#                 'volume': (0,),
#                 'rsi': (13,),
#                 'stochrsi': (13, 13, 13),
#                 'sma': (13,),
#                 'ema': (13,),
#                 'hma': None,
#                 'vwma': (13,),
#                 'momentum': None,  #(13,),
#                 'stochastic': None,  # (13, 3),
#                 'macd': None,  # (13,),
#                 'bollingerbands': (13,),
#                 'triangle': None,  # (13,),
#                 'fibonacci': None,  # (13,),
#                 'pivotpoint': None,  # (1,),
#                 'tomdemark': (9,),
#                 'atr': (20, 3),
#             },
#             'constants': {
#                 'rsi_low': 0.3,
#                 'rsi_high': 0.7,
#             },
#             'scores': {
#                 'rsi_factor': 1.0,
#                 'rsi_trend_factor': 0.5,
#                 'sma_ema_cross_factor': (-0.5, -0.5),  # no-div/div
#                 'ema_vwma_cross_factor': (-5, -5),
#                 'price_vwma_factor': 50.0,
#                 'ema_vwma_cross_bonus': 0,  # 1,2,3,5
#                 'rsi_ema_trend_div_factor': (-0.04, -0.04),
#             }
#         },
#         # {
#         #     'timeframe': Instrument.TF_MIN,
#         #     'sub-tf': Instrument.TF_TICK,
#         #     'mode': 'B',
#         #     'depth': 20,
#         #     'history': 20,  # 1440,  # 1 day
#         #     'score-ratio': 0.5,
#         #     'score-level': 0.05,
#         #     'indicators': {
#         #         'price': (1,),
#         #         'volume': (0,),
#         #         'rsi': (8,),
#         #         'stochrsi': (13, 13, 13),
#         #         'sma': (20,),
#         #         'ema': (8,),
#         #         'hma': (8,),
#         #         'vwma': (8,),
#         #         'momentum': None,  # (20,),
#         #         'stochastic': None,  # (9, 3),
#         #         'macd': None,  # (17,),
#         #         'bollingerbands': None,  # (26,),
#         #         'triangle': None,  # (20,),
#         #         'fibonacci': None, # (15,),
#         #         'tomdemark': (9,),
#         #     },
#         #     'constants': {
#         #         'rsi_low': 0.3,
#         #         'rsi_high': 0.7,
#         #     },
#         #     'scores': {
#         #         'rsi_factor': 0.04,
#         #         'rsi_trend_factor': 0.2,
#         #         'ema_vwma_cross_factor': 0.5,
#         #         'price_vwma_factor': 5.0,
#         #         'hma_sma_cross_factor': -50,
#         #         'hma_vwma_cross_factor': 0,
#         #         'ema_vwma_cross_bonus': 0.05,
#         #         'rsi_hma_trend_div_factor': -1.0,
#         #     }
#         # }
#     ]
# }
