import atexit
import datetime
import functools
import json
import os
import time

import tornado.ioloop
import tornado.web

from sprinkler import OpenSprinkler

NUMBER_OF_STATIONS = 8
DEBUG = True

class DelayCreateHandler(tornado.web.RequestHandler):

    def get(self, **kwargs):
        self.set_status(405)
        self.write(json.dumps({'error': 'GET is not supported for this endpoint'}))

    def post(self, _station, _hours):

        # Cast the station and hours to integers
        station = int(_station)
        hours = int(_hours)

        # Create the delay
        sprinkler.create_delay(station, hours)
        self.write({'response':'ok', 'error': None })


class DelayRemoveHandler(tornado.web.RequestHandler):

    def get(self, **kwargs):
        self.set_status(405)
        self.write(json.dumps({'error': 'GET is not supported for this endpoint'}))

    def post(self, _station=0):

        # Cast the station to an integer
        station = int(_station)

        # Remove the delay
        result = sprinkler.remove_delay(station)
        
        if result == True:
            self.write({ 'response': 'ok', 'error': None })
        else:
            self.set_status(404)
            self.write({ 'error': 'No delay was set on station %s' % _station })


class StationOnHandler(tornado.web.RequestHandler):

    def get(self, **kwargs):
        self.set_status(405)
        self.write(json.dumps({'error': 'GET is not supported for this endpoint'}))

    def post(self, _station, _minutes):

        # Cast the station and minutes to integers
        station = int(_station)
        minutes = int(_minutes)

        # Cancel any callbacks that would have been scheduled by currently
        # running jobs. We don't want them to fire, otherwise they would stop
        # the new job when they did
        if sprinkler.ioloop_timeout:
            tornado.ioloop.IOLoop.instance().remove_timeout(sprinkler.ioloop_timeout)

        # Calculate the callback delay in seconds
        delay = time.time() + (minutes * 60)

        # Operate the station
        result = sprinkler.operate_station(station, minutes)

        # Schedule the ioloop to call the done function when the operation is complete
        callback = functools.partial(sprinkler.stop_station, station)
        sprinkler.ioloop_timeout = tornado.ioloop.IOLoop.instance().add_timeout(delay, callback)

        if result == True:
            self.write({ 'response': 'ok', 'error': None })
        else:
            self.set_status(403)
            self.write({ 'error': 'Could not operate station. Delay or Standby in effect.' })


class StationOffHandler(tornado.web.RequestHandler):

    def get(self, **kwargs):
        self.set_status(405)
        self.write(json.dumps({'error': 'GET is not supported for this endpoint'}))

    def post(self, _station=0):

        # Cast the station to an integer
        station = int(_station)

        # Cancel any scheduled callbacks from currently running operations
        if sprinkler.ioloop_timeout:
            tornado.ioloop.IOLoop.instance().remove_timeout(sprinkler.ioloop_timeout)

        # Stop the station
        sprinkler.stop_station(station)
        self.write({ 'response': 'ok', 'error': None })


class StandbyHandler(tornado.web.RequestHandler):
    
    def get(self, **kwargs):
        self.set_status(405)
        self.write(json.dumps({'error': 'GET is not supported for this endpoint'}))

    def post(self, mode):
        
        if mode == 'create':
            result = sprinkler.create_standby()
            if result == True:
                self.write({ 'response': 'ok', 'error': None })
            else:
                self.set_status(403)
                self.write(json.dumps({'error': 'System is already in standby mode'}))
        
        elif mode == 'remove':
            result = sprinkler.remove_standby()
            if result == True:
                self.write({ 'response': 'ok', 'error': None })
            else:
                self.set_status(404)
                self.write(json.dumps({'error': 'System is not in standby mode'}))
        
        else:
            self.set_status(404)
            self.write(json.dumps({'error': 'Mode unknown'}))
        
    
class StatusHandler(tornado.web.RequestHandler):

    def get(self):

        # We're going to build up a dictionary of station statuses
        status = {}

        # Loop through each station and figure out if it's running, off, or delayed
        for station_number in range(1, sprinkler.number_of_stations+1):
            # See if a delay file exists
            if os.path.exists('DELAY-%d' % station_number):
                with open('DELAY-%d' % station_number) as f:
                    status[station_number] = { 'state': 'delayed','expires': f.read() }
            elif sprinkler.station_values[station_number-1] == 1:
                expiration = sprinkler.current_operation_complete
                status[station_number] = { 'state': 'running', 'expires': expiration }
            else:
                status[station_number] = { 'state':'off', 'expires': None }

        # Status is a dictionary so it will be returned as JSON
        self.write(status)


class HistoryHandler(tornado.web.RequestHandler):

    def get(self):

        # Open up the log file and get the contents
        with open('log.txt', 'r') as f:
            contents = f.readlines()

        # Get the last 100 lines of the contents
        last_lines = [line.strip().split("\t") for line in reversed(contents)][:100]

        # Split the tab-delimited line into an array of dictionaries
        line_dicts = [{'date': line[0], 'msg': line[1]} for line in last_lines]

        # Return the JSON-encoded list
        self.write(json.dumps(line_dicts))


class IndexHandler(tornado.web.RequestHandler):

    def get(self):
        self.write('<!-- Index goes here -->')


if __name__ == "__main__":

    app = tornado.web.Application([
        (r'/delay/(?P<_station>[1-8])/create/(?P<_hours>\d{1,})/', DelayCreateHandler),
        (r'/delay/(?P<_station>[1-8])/remove/', DelayRemoveHandler),
        (r'/delay/all/remove/', DelayRemoveHandler),
        (r'/history/', HistoryHandler),
        (r'/standby/(?P<mode>create)/', StandbyHandler),
        (r'/standby/(?P<mode>remove)/', StandbyHandler),
        (r'/station/(?P<_station>[1-8])/on/(?P<_minutes>30|[1-2][0-9]|[1-9])/', StationOnHandler),
        (r'/station/(?P<_station>[1-8])/off/', StationOffHandler),
        (r'/station/all/off/', StationOffHandler),
        (r'/status/', StatusHandler),
        (r'/', IndexHandler),
    ], debug=DEBUG)

    sprinkler = OpenSprinkler(debug=DEBUG, number_of_stations=NUMBER_OF_STATIONS)

    # Store a variable so we can make the IOLoop close a station when operation completes
    sprinkler.ioloop_timeout = None

    # Make sure all stations are off (in case the server was restarted in mid-run)
    sprinkler.reset_all_stations()

    # We want sprinkler.cleanup() to run when this script exits to make sure
    # no stations can be left in a running state
    atexit.register(sprinkler.cleanup)

    app.listen(8888)
    print "Server Started. Listening on port 8888"

    tornado.ioloop.IOLoop.instance().start()