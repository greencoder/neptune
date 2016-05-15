# Scheduler #

The system comes with a [a /utilities/scheduler.py](scheduler utility) to schedule sprinkler operations without cron. It reads a JSON file and schedules `at` jobs for any schedules that should be run that day.

*Note: You must have the Linux `at` program installed. Check this with the command `$ which at` and make sure it returns the path.*

## Syntax ##

The JSON syntax is fairly simple. This single entry will schedule station one to run for 15 minutes at 5:00am on Monday, Wednesday, and Friday:

```
[
    {
        "station": 1,
        "minutes": 15,
        "start": "05:00",
        "days": [
            "Monday",
            "Wednesday",
            "Friday"
        ]
    }
]
````

This file is saved as `scheduler/schedule.json`. Use the `--flag` command to tell the scheduler where the file is.

You can test your schedule file by passing the `--test` command:

```
$ python scheduler.py --file schedule.json --test

```

You can run the file multiple times; any queued `at` commands will be removed.

## Timezones ##

The scheduler will use your system's timezone when scheduling jobs. Make sure your system is set properly or adjust the times accordingly.

