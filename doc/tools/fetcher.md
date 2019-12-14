# Fetcher #

This command tools allow to fetch market data (ticks/trades or OHLC candles).

Each configured fetcher can be used throught the fetcher command tool.

Either you can fetch only a specific timeframe or only ticks/trades, or you can generate the higher timeframe,
in cascaded mode until the wanted higher timeframe.

The rebuilder command tools can be used after a fetch to rebuild a specific timeframe of OHLC, or many in casaced mode too.

...
