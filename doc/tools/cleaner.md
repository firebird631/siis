# Cleaner tool #

This tools allow to cleanup some data, complete or partially.

The mandatory option is the identifier of the broker : **--broker=**.
Other options are **--market=**, **--objects=**, **--from=**, **--to=** and **--timeframe=**.

For now only **--market=** option is supported.

If no arguments are specified any OHLCs for any market related to the specified broker are deleted from the database.
If market is specified, only OHLCs related to this market identifier are deleted.

You can bypass the confirmation message by adding the **--no-conf** argument.

The ticks/trades/quotes data files are not impacted by this tools at this time.
Furthers options could be added.
