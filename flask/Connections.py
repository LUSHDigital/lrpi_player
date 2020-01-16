from apscheduler.schedulers.background import BackgroundScheduler
from tinkerforge.ip_connection import IPConnection # pylint: disable=import-error
from time import sleep
import os

# brickd
HOST = os.environ.get("BRICKD_HOST", "127.0.0.1")
PORT = 4223

class Connections():
    def __init__(self):
        self.scheduler = BackgroundScheduler({
                            'apscheduler.executors.processpool': {
                                'type': 'processpool',
                                'max_workers': '1'
                            }}, timezone="Europe/London")

        self.tfIpCon = IPConnection()
        self.tfIpCon.connect(HOST, PORT)
        self.tfIDs = []
        self.tfIpCon.register_callback(IPConnection.CALLBACK_ENUMERATE, self.cb_enumerate)

        # Trigger Enumerate
        self.tfIpCon.enumerate()

        # Likely wait for the tinkerforge brickd to finish doing its thing
        sleep(0.7)

        print("tfIds before main loop: ", self.tfIDs)
        print("Starting scheduler...")
        self.scheduler.start(paused=False)

    def cb_enumerate(self, uid, connected_uid, position, hardware_version, firmware_version,
                    device_identifier, enumeration_type):
        self.tfIDs.append([uid, device_identifier])

