# @date 2023-08-19
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# dukascopy.com symbols and decimals

# @see https://www.dukascopy.com/swiss/french/cfd/range-of-markets/
# remove dot and slash from symbols to have identifier
# but have to test to determine the decimal place

DUKASCOPY_SYMBOLS_DECIMALS = {
    'USA500IDXUSD': 0.001,
    'USATECHIDXUSD': 0.001,
    'USA30IDXUSD': 0.001,
    'DEUIDXEUR': 0.001,
    'FRAIDXEUR': 0.001,
    'XAUUSD': 0.001,
    'AUDNZD': 0.00001,
    'AUDUSD': 0.00001,
    'EURCAD': 0.00001,
    'EURCHF': 0.00001,
    'EURGBP': 0.00001,
    'EURJPY': 0.001,
    'EURUSD': 0.00001,
    'GBPUSD': 0.00001,
    'USDCHF': 0.00001,
    'USDJPY': 0.001,
    # @todo complete FOREX, Oil, Silver, Commodities, Equities US,FR,DE...
    # BRENT.CMD/USD 1.00 brent oil
    # LIGHT.CMD/USD 1.00 brut oil
    # GAS.CMD/USD 0.1 gaz naturel
    # COPPER.CMD/USD 0.1 cuivre
    # DOLLAR.IDX/USD DXY
    # VOL.IDX/USD VOLIDXUSD VIX
    # BUND.TR/EUR BUNDTREUR Euro Bund
    # UKGILT.TR/GBP UKGILTTRGBP GBP Bund
    # USTBOND.TR/USD USTBONDTRUSD US Bond
    # US, FR, GER Equities ...
}
