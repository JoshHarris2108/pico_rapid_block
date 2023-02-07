import ctypes
import time
import numpy as np
import matplotlib.pyplot as plt
import h5py

from picosdk.ps5000a import ps5000a as ps
from picosdk.functions import adc2mV, assert_pico_ok, mV2adc

class PicoDevice():
    def __init__(self, handle, res, timebase):
        self.n_segments = 3
        self.n_captures = 3

        self.status = {}
        self.handle = ctypes.c_int16(handle)
        self.active_channels = []
        self.channel_ranges = []
        self.channel_buffers = []

        self.res = ps.PS5000A_DEVICE_RESOLUTION[res]
        self.max_adc = ctypes.c_int16()

        self.preTriggerSamples = 400
        self.postTriggerSamples = 100000
        self.maxsamples = self.preTriggerSamples + self.postTriggerSamples
        self.timebase = timebase

        self.time_interval_actual = ctypes.c_float()
        self.returnedMaxSamples = ctypes.c_int32()

        self.overflow = (ctypes.c_int16 * self.n_segments)()
        self.cmaxSamples = ctypes.c_int32(self.maxsamples)

        self.ready = ctypes.c_int16(0)
        self.check = ctypes.c_int16(0)

        self.Times = (ctypes.c_int64*self.n_segments)()
        self.TimeUnits = ctypes.c_char()

        self.start_time = None
        self.end_time = None

        self.TriggerInfo = None

        self.status["openunit"] = ps.ps5000aOpenUnit(ctypes.byref(self.handle), None, self.res)
        self.status["maximumValue"] = ps.ps5000aMaximumValue(self.handle, ctypes.byref(self.max_adc))
        self.status["MemorySegments"] = ps.ps5000aMemorySegments(self.handle, self.n_segments, ctypes.byref(self.cmaxSamples))
        self.status["SetNoOfCaptures"] = ps.ps5000aSetNoOfCaptures(self.handle, self.n_captures)
    
    def set_channel(self,status_string, channel, en, coupling, range, offset):
        ps_channel = ps.PS5000A_CHANNEL[channel]
        ps_coupling = ps.PS5000A_COUPLING[coupling]
        ps_range = ps.PS5000A_RANGE[range]
        self.status[status_string] = ps.ps5000aSetChannel(self.handle, ps_channel, en, ps_coupling, ps_range, offset)
        if en == 1:
            self.active_channels.append(channel)
            self.channel_ranges.append(range)

    def set_simple_trigger(self, channel, range, threshold_mv,):
        source = ps.PS5000A_CHANNEL[channel]
        threshold = int(mV2adc(threshold_mv,(ps.PS5000A_RANGE[range]),self.max_adc))
        self.status["trigger"] = ps.ps5000aSetSimpleTrigger(self.handle, 1, source, threshold, 2, 0, 1000)

    def generate_buffers(self):
        for i in range(len(self.active_channels)):
            self.channel_buffers.append(np.empty((self.n_captures,self.maxsamples),dtype=np.int16))

        for c,b in zip(self.active_channels,self.channel_buffers):
            print(f'Channel {c}')
            source_chan = ps.PS5000A_CHANNEL[c]
            for i in range(len(b)):
                buffer = b[i]
                self.status[f"SetDataBuffer_{c}_{i}"] = ps.ps5000aSetDataBuffer(self.handle, source_chan, buffer.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)), self.maxsamples, i, 0)

    def run_block(self):
        self.status["GetTimebase"] = ps.ps5000aGetTimebase2(self.handle, self.timebase, self.maxsamples, ctypes.byref(self.time_interval_actual), ctypes.byref(self.returnedMaxSamples), 0)
        self.status["runblock"] = ps.ps5000aRunBlock(self.handle, self.preTriggerSamples, self.postTriggerSamples, self.timebase, None, 0, None, None)
        while self.ready.value == self.check.value:
            self.status["isReady"] = ps.ps5000aIsReady(self.handle, ctypes.byref(self.ready))
        self.status["GetValuesBulk"] = ps.ps5000aGetValuesBulk(self.handle, ctypes.byref(self.cmaxSamples), 0, (self.n_segments-1), 0, 0, ctypes.byref(self.overflow))
        self.end_time = time.time()

    def get_trigger_info(self):
        self.status["GetValuesTriggerTimeOffsetBulk"] = ps.ps5000aGetValuesTriggerTimeOffsetBulk64(self.handle, ctypes.byref(self.Times), ctypes.byref(self.TimeUnits), 0, (self.n_segments-1))
        TriggerInfo = (ps.PS5000A_TRIGGER_INFO*self.n_captures)()
        self.status["GetTriggerInfoBulk"] = ps.ps5000aGetTriggerInfoBulk(self.handle, ctypes.byref(TriggerInfo), 0, (self.n_captures-1))
        for i in TriggerInfo:
            print("PICO_STATUS is ", i.status)
            print("segmentIndex is ", i.segmentIndex)
            print("triggerTime is ", i.triggerTime)
            print("timeUnits is ", i.timeUnits)
            print("timeStampCounter is ", i.timeStampCounter)

    def plot_captures(self):
        overflow_count = 0
        not_overflow_count = 0
        print(f"Time from running block mode to accessing buffers in plot_capture() {self.end_time-self.start_time}")
              
        for c,b in zip(self.active_channels,self.channel_buffers):
            print(f'Channel {c}')
            for i in range(len(b)):
                print(b)
                buffer = b[i]
                #print(buffer[0:20])
                if (i == self.n_captures - 2):
                    print(i)
                    plt.plot(buffer[:])
                    plt.show()

        # for i in self.overflow:
        #     if self.overflow[i] == 1:
        #         overflow_count += 1
        #     if self.overflow[i] == 0:
        #         not_overflow_count += 1
        #     print(f"Overflows: {overflow_count} Not Overflowed: {not_overflow_count}")

    def write_to_file(self):

        ### Items needed for converting ADC counts back to mv and plotting time values ###
        # - buffer of data 
        # - individual channel range
        # - maxADC of whole system
        # - sample interval in ns
        # - maxsamples (can probably be gotten from the length of the dataset once reading the file and doesnt need to be saved)
        
        metadata = {
            'time_interval_actual': self.time_interval_actual,
            'max_adc': self.max_adc,
            'active_channels': self.active_channels[:],
            'channel_ranges': self.channel_ranges[:]
        }

        with h5py.File('/tmp/data.hdf5','w') as f:
            metadata_group = f.create_group('metadata')
            for key, value in metadata.items():
                metadata_group.attrs[key] = value

            for c,b in zip(self.active_channels,self.channel_buffers):
                f.create_dataset(('adc_counts_'+c), data = b)

    def stop_scope(self):
        self.status["stop"] = ps.ps5000aStop(self.handle)
        self.status["close"] = ps.ps5000aCloseUnit(self.handle)

    def run_capture(self):
        self.start_time = time.time()
        self.generate_buffers()
        self.run_block()
        self.write_to_file()
        self.stop_scope()
