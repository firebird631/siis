# Notifiers #

THe notifiers offers the possibility to send notification to external services and to the system desktop.
It can notify of signals, trades, accounts and system reports.

Different externals services can be notified :

* [Desktop](desktop.md)
* [Android](android.md) 
* [Discord](discord.md)
* [Telegram](telegram.md)
* [Xmpp](xmpp.md)

### Configuration ###

Each notifier can be configured per profile, in the "notifiers": {} map section.
In addition, each notifier has a specific configuration file in config/notifiers/ directory,
with a possible overriding in the user config directory.

## Desktop ##

By default, the desktop notifier is always initiated, but on VPS dBus will not be available, neither audio support.
It is possible to disable it from a profile.

* Display system desktop popup notification using D-Bus on Linux
* Play audio alerts using aplay (alsa player) on Linux
* Not support for Windows desktop for now
* Customizable audio alerts at user level and at profile level

[More details of the Desktop notifier...](desktop.md)

## Android (tm) (c) Google ##

An Android application is in development, and allow receiving notifications using the Firebase API.
This application could be used to receive public signals, or to receive your own private notification using your private auth-key.

[More details of the Android (tm) notifier...](android.md)

## Discord (tm) (c) ##

Only webhooks supported. Help is welcome to use Discord API for more advanced features.

[More details of the Discord (tm) notifier...](discord.md)

## Telegram (tm) (c) ##

Planned support, help is welcome.

[More details of the Telegram (tm) notifier...](telegram.md)

## Xmpp (open-source protocol) ##

Planned support, help is welcome.

[More details of the XMPP notifier...](xmpp.md)
