# Data structure #

## Market dataset ##

The siis folder contains a subdirectory : markets. Into this directory the structure remains the same for any exchange (configured trader) :

<name_of_trader>/<market_name>/T/<year_month_market_name>

With :
  * <name_of_trader> : name of the related trader
    * For example binance.com, binancefutures.com, kraken.com, ig.com ...
  * <market_name> : name of the pair or the market codename related to the exchange
    * For example BTCUSDT, XRPUSD, ADAEUR, EURUSD, UDSJPY ...
  * T : means ticks or trades data or aggregated trade data
  * <year_month_market_name> : 4 digits year, 2 digits month, market name or codename
    * The file extension can be empty or .dat
      * .dat extension means an optimized binary file, this is the default configured file format

For Binance data are aggregate trades, for BitMex data are real trade, for IG CFD data are ticks,
for Kraken data are real trades.

There is one file per month, there is a binary and a tabular version of the file at this time. But maybe later
the tabular version will be removed.

## Ticks/trade ##

...

## OHLC/candles ##

...

## User strategy persistence ##

...

## Trades persistence ##

...

## Liquidation ##

...

## Performance and optimization ##

...

## Considerations about organisation ##

...
