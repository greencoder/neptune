ospi-neptune
============

A Tornado-based web API to control the OpenSprinkler Pi

**Disclaimer: This software is very alpha. Don't blame me if your yard is turned into a lake. There are a few built-in safeguards, but please use at your own risk and test thoroughly before you go on a month-long vacation. This software is running at my house, but your mileage may vary.**

# Server Usage #

The server can be run in the foreground if you want to test and debug:

```
$ sudo python server.py
````

Use `Ctrl-C` to shut down the server gracefully.

*Note: You must prefix the command with `sudo` when you run it on the Raspberry Pi, as it requires access to the GPIO pins.*

It is possible to run the server in the background from the command line and keep it running when you log out:

```
$ nohup sudo python server.py &
```

While this does work, the server will not start automatically when the Raspberry Pi boots. Consider something like `upstart` or `supervisor` to run the server automatically.

# Basic Operation #

The following sections demonstrate how to issue API commands to the system.

## Starting a station ##

To operate a station, use the `/station/{{ station number }}/on/{{ minutes }}/` endpoint with POST. To operate station number 1 for 15 minutes:

```
$ curl -X POST http://localhost:8888/station/1/on/15/
```

*Note: You can issue the `on` command to a new station while a station is running. It will stop the running station and start the new one.*

If you attempt to run a station that has a delay in effect, you will receive a `403` error.

## Stopping a station ##

To turn off a running station, use the `/station/{{ station number }}/off/` endpoint with POST. To turn off station number 1:

```
$ curl -X POST http://localhost:8888/station/1/off/
```

Due to a limitation with the hardware, you will not receive an error if you stop a station that is not running. In actuality, issuing the `off` command to a numbered station will stop *any* running station. (For example, if station 1 is running and you issue the `/station/2/off/` command, station number 1 will stop) This is because the hardware allows no way to query which station is running.


## Viewing station statuses ##

To see the current status of all stations, use the `/status/` endpoint:

```
$ curl http://localhost:8888/status/
```

## Preventing a station from running (adding delay) ##

To prevent a station from operating for a number of hours, use the `/delay/{{ station number }}/create/{{ hours }}/` endpoint with POST. To prevent station number 1 for running for the next 24 hours:

```
$ curl -X POST http://localhost:8888/delay/1/create/24/
```

*Note: Setting a delay on a station will overwrite any existing delay.*

When you set a delay, a `DELAY-{{ station number }}` file is created. These files are automatically removed when they expire. 

## Removing a delay ##

To cancel an existing delay, use the `/delay/{{ station number }}/remove/` endpoint with POST. To remove the delay for station 1:

```
$ curl -X POST http://localhost:8888/delay/1/remove/
```

There is a convenience endpoint for removing all delay files:

```
$ curl -X POST http://localhost:8888/delay/all/remove/
```

If you try to remove a delay that isn't set, you will receive a `404` error. Using the `/delay/all/remove/` endpoint will only return a `200` response, whether or not it found any delay files.

As mentioned above, you do not have to remove delay files if you let them expire.

## Standby Mode ##

You can put the system in a perpetual (non-expiring) standby mode by using the `/standby/create/` endpoint with POST:

```
$ curl -X POST http://localhost:8888/standby/create/
````

If you attempt to set standby mode when it is already set, you will receive a `403` error.

You can remove standby mode by using the `/standby/remove/` endpoint with POST:

```
$ curl -X POST http://localhost:8888/standby/remove/
````

If you attempt to remove standby mode when it is not set, you will receive a `404` error.

Standby mode works by putting a file named `STANDBY` in the root directory. You can create or remove this file yourself instead of using the API. `STANDBY` files never expire.

# Scheduling Operations #

There are a couple of ways to schedule sprinkler operations:

## Using cron ##

The easiest way to schedule jobs is to use `cron`. For example, you could run station 1 for 15 minutes at 5am on Mondays, Wednesdays, and Fridays like this:

```
00 05 * * 1,3,5 curl -X POST http://localhost:8888/station/1/on/15/
```

## Using the Optional Scheduler ##

The system also comes with a scheduler that reads a JSON file to schedule sprinkler operations. See the (scheduler documentation)[a docs/scheduler.md] for details.

## Trimming log files ##

The system does not use Python logging, it just writes to a `log.txt` file. Use this cron job to trim the logs to 1000 lines:

```
@daily cd <code directory> && tail -1000 log.txt > log.tmp && mv log.tmp log.txt
```

# Feedback #

I welcome any feedback or advice you are willing to offer. You can use the issues tab in Github or reach out to me at snewman18 [at gmail dot com].

# License #

This project is distributed under the MIT license. Do whatever you want with it, but please provide attribution back and don't hold me liable.

