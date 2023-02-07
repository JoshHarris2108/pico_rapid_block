import signal
import threading
import numpy as np

from pico import PicoDevice


class RapidBlockExample():

    def __init__(self):

        self.pico_device = PicoDevice(0,"PS5000A_DR_12BIT",2)

        self.pico_device.set_channel("setChA","PS5000A_CHANNEL_A", 1,"PS5000A_DC","PS5000A_20V",0.0)
        self.pico_device.set_channel("setChB","PS5000A_CHANNEL_B", 1,"PS5000A_DC","PS5000A_20V",0.0)
        self.pico_device.set_channel("setChB","PS5000A_CHANNEL_C", 0,"PS5000A_DC","PS5000A_20V",0.0)
        self.pico_device.set_channel("setChB","PS5000A_CHANNEL_D", 0,"PS5000A_DC","PS5000A_20V",0.0)
        self.pico_device.set_simple_trigger("PS5000A_CHANNEL_A","PS5000A_20V",500)

        self.pico_thread = threading.Thread(target=self.pico_device.run_capture)

        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, sig, frame):
        print("Stopping data acquisition/saving")
        pass

    def run(self):
        self.pico_thread.start()

if __name__ == '__main__':

    streamer = RapidBlockExample()
    streamer.run()
