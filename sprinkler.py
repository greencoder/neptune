import arrow
import datetime
import os
import sys

CUR_DIR = os.path.dirname(os.path.realpath(__file__))

try:
    import RPi.GPIO as GPIO
except ImportError:

    # GPIO is only available on the PI, so these stub out the 
    # required methods for development purposes
    print "** GPIO Not Found. Running in demo mode **"

    class MockGPIO():
        def __init__(self):
            self.BCM = 0
            self.OUT = 0
            self.RPI_REVISION = 2

        def cleanup(self):
            return

        def setmode(self, mode):
            return

        def setup(self, pin, mode):
            return

        def output(self, pin, value):
            return

    GPIO = MockGPIO()


class OpenSprinkler():

    ### Low-Level Hardware Stuff. Don't mess with these. ###

    def _enable_shift_register_output(self):
        """
        Low-level function to enable shift register output. Don't call this
        yourself unless you know why you are doing it.
        """
        GPIO.output(self.PIN_SR_NOE, False)

    def _disable_shift_register_output(self):
        """
        Low-level function to disable shift register output. Don't call this
        yourself unless you know why you are doing it.
        """
        GPIO.output(self.PIN_SR_NOE, True)

    def _set_shift_registers(self, new_values):
        """
        This is the low-level function that is called to set the shift registers.
        I don't pretent do understand the inner workings here, but it works. Don't
        use this to turn on/off stations, use set_station_status() as the
        higher-level interface.
        """
        GPIO.output(self.PIN_SR_CLK, False)
        GPIO.output(self.PIN_SR_LAT, False)

        for s in range(0, self.number_of_stations):
            GPIO.output(self.PIN_SR_CLK, False)
            GPIO.output(self.PIN_SR_DAT, new_values[self.number_of_stations-1-s])
            GPIO.output(self.PIN_SR_CLK, True)

        GPIO.output(self.PIN_SR_LAT, True)

        # Update the status
        self._update_status()

    def _initialize_hardware(self):
        """
        This contains the low-level stuff required to make the GPIO operations work. Someone
        smarter than me wrote this stuff, I just smile and nod.
        """
        self.PIN_SR_CLK = 4
        self.PIN_SR_NOE = 17
        self.PIN_SR_LAT = 22
        self.PIN_SR_DAT = 21

        # The 2nd revision of the RPI has a different pin value
        if GPIO.RPI_REVISION == 2:
            self.PIN_SR_DAT = 27

        # Not sure why this is called, but it was in the original script.
        GPIO.cleanup()

        # setup GPIO pins to interface with shift register. Don't muck with this
        # stuff unless you know why you are doing it.
        GPIO.setmode(GPIO.BCM)

        GPIO.setup(self.PIN_SR_CLK, GPIO.OUT)
        GPIO.setup(self.PIN_SR_NOE, GPIO.OUT)

        self._disable_shift_register_output()

        GPIO.setup(self.PIN_SR_DAT, GPIO.OUT)
        GPIO.setup(self.PIN_SR_LAT, GPIO.OUT)

        self._set_shift_registers(self.station_values)
        self._enable_shift_register_output()

    ### Convenience methods for filesystem operations. You don't need to call these
    ### manually, they are handled by the higher-level operations.

    def _update_status(self):
        """
        Updates the STATUS ivar with the value for each station
        """
        self.status = "%s" % "".join([str(s) for s in self.station_values])

    ### PID File Handling ###

    def _create_pid_file(self, minutes_to_run):
        """
        Writes a PID file to the directory to indicate what the PID of the
        current program is and when it expires.
        """
        expiration = arrow.utcnow().replace(minutes=+minutes_to_run).isoformat()
        file_path = os.path.join(CUR_DIR, '%s.pid' % self.pid)
        self.log("Creating pid file: %s" % file_path)
        with open(file_path, 'w') as f:
            f.write("%s" % expiration)

    def _remove_pid_file(self):
        """
        Handles removal of the PID file.
        """
        file_path = os.path.join(CUR_DIR, '%s.pid' % self.pid)
        self.log("Removing pid file: %s" % file_path)
        if os.path.exists(file_path):
            os.remove(file_path)

    ### Station Operation ###

    def cleanup(self):
        """
        This runs at the termination of the file, turning off all stations, making
        sure that any PID files are removed, and running GPIO cleanup.
        """
        self.log("Running Cleanup.")
        self.reset_all_stations()
        self._remove_pid_file()
        GPIO.cleanup()

    def stop_station(self, station_number):
        """
        This method stops a station (actually, any stations)
        """
        self.log('Stopping station %s.' % station_number)
        self._remove_pid_file()
        self.reset_all_stations()

    def operate_station(self, station_number, minutes):
        """
        This is the method that operates a station. Running it causes any
        currently-running stations to turn off, then a pid file is created that
        lets the system know that there is a process running. When it completes,
        ALL stations are turned off and the file is cleaned up.
        """
        self.log("Operating station %d for %d minutes." % (station_number, minutes))

        # Check to see if the system is in standby mode
        if self.check_for_standby():
            self.log('Standby mode is in effect. Job will not run.')
            return False

        # Check to see if a delay is in effect
        delay = self.check_for_delay(station_number)
        if delay:
            self.log("Delay in effect until %s. Job will not run." % delay)
            return False

        # First, set all stations to zero
        self.station_values = [0] * self.number_of_stations

        # Next, enable just the station to run (adjusting for 0-based index)
        try:
            self.station_values[station_number-1] = 1
        except IndexError:
            self.log("Invalid station number %d passed. Skipping." % station_number)

        # Keep track of when this operation will complete
        self.current_operation_complete = arrow.utcnow().replace(minutes=+minutes).isoformat()

        # Send the command
        self._set_shift_registers(self.station_values)

        # Create a filesystem flag to indicate that the system is running
        self._create_pid_file(minutes)
        
        return True

    def reset_all_stations(self):
        """
        A convenience method for turning everything off.
        """
        self.log("Reset Command Received. Turning Off All Stations.")
        off_values = [0] * self.number_of_stations
        self.station_values = off_values
        self._set_shift_registers(off_values)
        self.current_operation_complete = None

    ### Delay Handling ###

    def remove_delay(self, station):
        """
        Removes a delay file for a station. If station is zero,
        then we need to remove all delay files.
        """
        if station == 0:
            # 0 is the number for "all stations"
            self.log('Removing all delay files')
            pid_files = [f for f in os.listdir(CUR_DIR) if f.startswith("DELAY-")]
            for pid_file in pid_files:
                os.remove(pid_file)
            return True
        else:
            self.log("Removing delay file for station %d" % station)
            delay_file_path = 'DELAY-%d' % station
            if os.path.exists(delay_file_path):
                os.remove(delay_file_path)
                return True
            else:
                return False

    def create_delay(self, station, hours):
        """
        Creates a delay file for a specific station that expires after the number of hours passed
        """
        # Calculate what the datetime object will be by adding the current time
        # and the number of hours to delay. This will be the body of the DELAY file.
        expiration = arrow.utcnow().replace(hours=+hours).isoformat()

        # Write out the DELAY file and make the body the expiration time.
        self.log("Creating delay file for station %d with expiration %s" % (station, expiration))

        delay_file_path = os.path.join(CUR_DIR, 'DELAY-%d' % station)
        with open(delay_file_path, 'w') as f:
            f.write(expiration)

        return True

    def create_standby(self):
        """
        Creates a file called STANDBY in the root directory. This file
        prevents all station operations.
        """
        standby_file_path = os.path.join(CUR_DIR, 'STANDBY')
        
        # If the file already exists, return false
        if os.path.exists(standby_file_path):
            return False
        else:
            with open(standby_file_path, 'w') as f:
                f.write('%s' % datetime.datetime.now())
            return True

    def remove_standby(self):
        """
        Removes the file called STANDBY in the root directory.
        """
        standby_file_path = os.path.join(CUR_DIR, 'STANDBY')
        if os.path.exists(standby_file_path):
            os.remove(standby_file_path)
            return True
        else:
            return False

    def check_for_standby(self):
        """
        Look at the filesystem to see if a STANDBY file exists.
        """
        standby_file_path = os.path.join(CUR_DIR, 'STANDBY')
        return os.path.exists(standby_file_path)

    def check_for_delay(self, station):
        """
        Look at the filesystem to see if a DELAY file exists for a station. If the
        file does exist, open it up to see if it's expired. If so, remove the file.
        """
        delay_file_path = os.path.join(CUR_DIR, 'DELAY-%d' % station)

        # If the delay file exists, see if it's valid
        if os.path.exists(delay_file_path):

            # Read the file so we can inspect the contents
            with open(delay_file_path, 'r') as f:
                data = f.read()

            # The file might have a bad value. Check carefully.
            try:
                # Try to turn the body into a datetime object
                expiration = arrow.get(data)
                # If the expiration time is less than now (i.e. it has passed) remove the file
                if arrow.utcnow() >= expiration:
                    self.log("Found expired delay file for station %d. Removing." % station)
                    os.remove(delay_file_path)
                else:
                    return expiration.isoformat()
            except ValueError:
                # If we can't cast the value of the file into a date object, there is
                # no sense keeping the file around. Deleate it.
                self.log("Could not read date in delay file. Removing file.")
                os.remove(delay_file_path)
                return None
        else:
            return None

    ### Logging ###

    def log(self, message):
        now_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        msg = '%s\t\t%s\n' % (now_time, message)
        file_path = os.path.join(CUR_DIR, 'log.txt')
        print msg.strip()
        with open(file_path, 'a') as f:
            f.write('%s\t\t%s\n' % (now_time, message))


    def __init__(self, debug=False, number_of_stations=8):

        self.number_of_stations = number_of_stations

        # If debug is true, we print log messages to console
        self.debug = debug

        # We need to save the PID of the current process.
        self.pid = os.getpid()

        # Initial values are zero (off) for all stations.
        self.station_values = [0] * number_of_stations

        # When an operation runs, we store the time it will complete
        self.current_operation_complete = None

        # Keep a running status of the current stations
        self._update_status()

        # Get the hardware ready for operations
        self._initialize_hardware()


if __name__ == "__main__":
    sys.exit('This file cannot be run directly.')

