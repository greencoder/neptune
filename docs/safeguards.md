# Safeguards #

To prevent a station from running indefinitely due to a software error, a few safeguards have been put into place.

## Reset on Start ##

When the server starts, the first thing it does is reset all stations to off. This ensures that if the server was restarted mid-run, all stations will be turned off. (This is especially handy when you use supervisor or upstart to automatically restart the server if it crashes)

## Process Identifier ##

When a station start running for *N* minutes, Tornado schedules code to execute at the end of *N* minutes to stop the station via the Tornado IOLoop. Under ideal circumstances, this works well turn turn off the hardware at the end of the run.

Being defensive against problems, the software also writes a `<process number>.pid` file to the filesystem. This file is named with the process identifier of the running server and contains an ISO 8601 timestamp of when the station is supposed to complete.

For example, when you start a station for 15 minutes and the process identifier of `server.py is `14748`, a file named `14748.pid` will be created in the root of the project. That file will contain a UTC timestamp of the end time for the run:

```
2016-05-14T22:09:48.172993+00:00
```

The file will automatically be deleted when the station stops. If the file does not delete, that would indicate that there was a problem.

Use the `utilities/check_pids.py` file to look for `.pid` files that are still present after they should have been deleted. If it finds one, it will stop all stations and log the error.

## Checking for runaway stations ##

When a station starts, a `.pid` file is created when a station starts containing the time the station should complete. Running `utilities/check_pids.py` will check for overdue `.pid` files and stop all stations if necessary.

It would be advisable to run `check_pids.py` several times per hour to check for problems. To make it run every 15 minutes with cron:

```
*/15 * * * * /path/to/python /path/to/code/utilites/check_pids.py
```

