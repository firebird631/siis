# Exporter tool #

This tool can export data for a specific market of a specific broker, for a specific or any timeframe and into a specified range of date.

Only the SIIS 1.0.0 format is supported for now.

## SIIS 1.0.0 ##

Why ? The idea is to easily have dump of data, and simply import them later.


### Format ###

Its a text file, really simple, the first row is the manifest of the file,
Each element is seperated by a tab. The header is a list of key=value.

There is one ore more block of OHLCs, preceded by a timeframe=value row.
The timeframe=value row defined the timeframe of the following OHLCs, or ticks/trades/quotes.


### Options ###

* --broker= Mandatory, identifier of the broker
* --market= Mandatory, identifier of the market
* --from= Optional, datetime of the range from
* --to= Optional, datetime of the range to
* --timeframe= Optional, specific timeframe else will export any timeframes from 1m, to 1M
* --filename= Mandatory, Destination path or prefix for the filename

The filename will be created into the current working directory, or a path must be specified.
The filename options must be terminated by a prefix.
If there is only a prefix, the file will be created into the current working directory.

The file is overwritten, not append, take care then this will erase the previous file if it exists.

Example :

```
python siis.py real --export --broker=ig.com --market=CS.D.EURUSD.MINI.IP --filename=full-
```

Will export any timeframe for the market CS.D.EURUSD.MINI.IP of broker ig.com.
The filename is prefixed by **full-**.
