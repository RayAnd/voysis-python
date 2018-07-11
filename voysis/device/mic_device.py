import sys
import threading

import pyaudio

from voysis.device.device import Device

is_py2 = sys.version[0] == '2'
if is_py2:
    import Queue as Queue
else:
    import queue as Queue


class MicDevice(Device):
    def __init__(self, **kwargs):
        Device.__init__(self)
        self.pyaudio_instance = pyaudio.PyAudio()
        self.queue = Queue.Queue()
        self.quit_event = threading.Event()
        self.channels = kwargs.get('channels', 1)
        self.sample_rate = kwargs.get('sample_rate', 16000)
        self.audio_format = kwargs.get('audio_format', pyaudio.paInt16)
        self.device_index = None

    def _callback(self, in_data, frame_count, time_info, status):
        self.queue.put(in_data)
        return None, pyaudio.paContinue

    def start_recording(self):
        self.stream = self.pyaudio_instance.open(
            input=True,
            start=False,
            format=self.audio_format,
            channels=self.channels,
            rate=self.sample_rate,
            frames_per_buffer=self.chunk_size,
            stream_callback=self._callback,
            input_device_index=self.device_index
        )
        self.quit_event.clear()
        self.queue.queue.clear()
        self.stream.start_stream()

    def stop_recording(self):
        self.stream.stop_stream()
        self.quit_event.set()

    def is_recording(self):
        return not(self.quit_event.is_set())

    def generate_frames(self):
        self.quit_event.clear()
        try:
            while not self.quit_event.is_set():
                try:
                    frames = self.queue.get(block=False)
                    if not frames:
                        break
                    yield frames
                except Queue.Empty:
                    pass
        except StopIteration:
            self.stream.close()
            self.pyaudio_instance.terminate()
            raise
        raise StopIteration()

    def audio_type(self):
        return "audio/pcm;bits={};rate={}".format(
            pyaudio.get_sample_size(self.audio_format) * 8,
            self.sample_rate)
