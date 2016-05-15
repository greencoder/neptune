import argparse
import datetime
import json
import os
import sys

CUR_DIR = os.path.dirname(os.path.realpath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(CUR_DIR, os.pardir))
LOG_FILE_PATH = os.path.join(PARENT_DIR, 'log.txt')

SERVER_HOST = 'localhost'
SERVER_PORT = '8888'

class Event():
    
    def __init__(self, event_dict):
        try:
            self.start_time = event_dict['start']
            self.minutes = event_dict['minutes']
            self.station = event_dict['station']
            self.days = self.day_names_to_numbers(event_dict['days'])
        except KeyError, e:
            sys.exit('Error reading schedule. Missing key: %s' % e)

    def __repr__(self):
        day_list = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
        days = ", ".join([day_list[day-1] for day in self.days])
        return "Station %d, run %d minutes on %s @ %s" % \
            (self.station, self.minutes, days, self.start_time)

    def day_names_to_numbers(self, days):
        """
        Takes Day Names and Converts them to ISO Weekdays
        (Monday is 1 and Sunday is 7)
        """
        names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        return [names.index(day)+1 for day in days]

    def should_run_today(self):
        """
        Compares the current day number and time to the event to see 
        if it's supposed to be running today.
        """
        now = datetime.datetime.now()
        day = now.isoweekday()

        # See if today is in the list of days to run
        if day in self.days:
            now_hour_min = now.strftime("%H:%M")
            if now_hour_min < self.start_time:
                return True

        # If none of the tests passed, we do not run
        return False

    @classmethod
    def log(self, message):
        """
        A convenience method for writing operations to a log file.
        """
        file_path = os.path.join(PARENT_DIR, 'log.txt')
        f = open(LOG_FILE_PATH, 'a')
        now_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        msg = '%s\t\t%s\n' % (now_time, message)
        f.write(msg)
        print msg


if __name__ == "__main__":

    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True)
    parser.add_argument("--test", action="store_true", dest="test", default=False)
    args = vars(parser.parse_args())

    # Try to open up the filename that was passed
    try:
        file_path = os.path.abspath(args['file'])
        f = open(file_path, 'r')
        data = f.read()
        f.close()
    except IOError:
        sys.exit("Error opening schedule file: %s" % file_path)

    # Turn the contents of the json file into a Python list
    try:
        events = json.loads(data)
    except ValueError:
        sys.exit("Error in schedule.json syntax. Invalid JSON.")

    if type(events) is not list:
        sys.exit("Error in schedule.json syntax. Could not find events list.")

    # If we get a dump flag, we just want to output the schedule 
    if args['test']:
        for item in events:
            print Event(item)
        sys.exit()

    # Remove any queued events (in case this is run multiple times)
    os.system('for i in `atq | awk \'{print $1}\'`;do atrm $i;done')
    
    # Loop over all the events and find ones that should be scheduled today
    for item in events:

        # Turn the event dictionary into an object
        event = Event(item)

        # See if the event is supposed to run today
        if event.should_run_today():

            Event.log("Scheduling event: Run station %s for %s minutes today at %s" % (event.station, 
                event.minutes, event.start_time))

            url = 'http://%s:%s/station/%s/on/%s/' % (SERVER_HOST, SERVER_PORT, 
                event.station, event.minutes)

            os.system('echo "curl -s -X POST %s >/dev/null 2>&1" | at %s today' % (url, event.start_time))
