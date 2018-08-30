import datetime
import sys
import time
from voysis.device.device import Device

if sys.version[0] == '2':
    import Queue as queue
else:
    import queue


class FileDevice(Device):
    def __init__(self, wav_file=None, **kwargs):
        Device.__init__(self)
        self.time_between_chunks = kwargs.get('time_between_chunks', 0.08)
        self._queue = queue.Queue()
        self._last_chunk_time = datetime.datetime.utcfromtimestamp(0)
        self.wav_file = wav_file

    def stream(self, client, recording_stopper):
        self.start_recording()
        recording_stopper.started()
        query = client.stream_audio(self.generate_frames(), notification_handler=recording_stopper.stop_recording,
                                    audio_type=self.audio_type())
        recording_stopper.stop_recording(None)
        return query

    def start_recording(self):
        self._queue.queue.clear()
        self.wav_to_frames()

    def stop_recording(self):
        self._queue.queue.clear()

    def is_recording(self):
        return not(self._queue.empty())

    def generate_frames(self):
        while not self._queue.empty():
            data = self._queue.get_nowait()
            if data:
                now = datetime.datetime.utcnow()
                seconds_since_last = (now - self._last_chunk_time).total_seconds()
                if seconds_since_last < self.time_between_chunks:
                    time.sleep(self.time_between_chunks - seconds_since_last)
                self._last_chunk_time = now
                yield data

    def wav_to_frames(self):
        while True:
            data = self.wav_file.read(self.chunk_size)
            if not data:
                break
            self._queue.put(data)

    def audio_type(self):
        return 'audio/pcm;bits=16;rate=16000'
