import abc
import datetime
import queue
import time

from voysis.audio.audio import AudioFile
from voysis.audio.audio import PCM_SIGNED_INT
from voysis.device.device import Device


class FileDevice(Device):
    def __init__(self, audio_file=None, **kwargs):
        Device.__init__(self, **kwargs)
        self.time_between_chunks = kwargs.get('time_between_chunks', 0.08)
        self._queue = queue.Queue()
        self._last_chunk_time = datetime.datetime.utcfromtimestamp(0)
        self.audio_file = AudioFile(audio_file)
        if self.audio_file.header is not None:
            self.encoding = self.audio_file.header.encoding
            self.sample_rate = self.audio_file.header.sample_rate
            self.bits_per_sample = self.audio_file.header.bits_per_sample
            self.channels = self.audio_file.header.channels
            self.big_endian = self.audio_file.header.big_endian
        else:
            self.encoding = None
            self.sample_rate = None
            self.bits_per_sample = None
            self.channels = None
            self.big_endian = None

    def stream(self, client, recording_stopper):
        self.start_recording()
        recording_stopper.started()
        query = client.stream_audio(self.generate_frames(), notification_handler=recording_stopper.stop_recording,
                                    audio_type=self.audio_type())
        recording_stopper.stop_recording(None)
        return query

    def start_recording(self):
        print(
            f'Sending {self.channels} channels at {self.sample_rate}Hz, {self.bits_per_sample} bits per sample'
            f' using encoding {self.encoding}'
        )
        self._queue.queue.clear()
        self.audio_to_frames()

    def stop_recording(self):
        self._queue.queue.clear()

    def is_recording(self):
        return not (self._queue.empty())

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

    def audio_to_frames(self):
        while True:
            data = self.audio_file.read(self.chunk_size)
            if not data:
                break
            self._queue.put(data)

    @abc.abstractmethod
    def audio_type(self):
        pass


class RawFileDevice(FileDevice):
    """
    File device for sending raw samples from a file to the service. If the
    file being sent is a valid wav file, the audio details will be read from
    the wav header (the wav header will be stripped and not sent to the
    server). If the file is raw samples, the audio format details will be
    taken from the command line or, if not provided, default to
    16KHz, little-endian, signed integer, 1 channel PCM.
    """
    def __init__(self, audio_file=None, **kwargs):
        super().__init__(audio_file, **kwargs)
        if self.audio_file.header is None:
            self.encoding = kwargs.get('encoding', PCM_SIGNED_INT)
            self.sample_rate = kwargs.get('sample_rate', 16000)
            self.bits_per_sample = 16 if self.encoding == PCM_SIGNED_INT else 32
            self.channels = 1
            self.big_endian = kwargs.get('big_endian', False)

    def audio_type(self):
        return f'audio/pcm;encoding={self.encoding};bits={self.bits_per_sample};rate={self.sample_rate}' \
               f';channels={self.channels};big-endian={self.big_endian}'


class WavFileDevice(FileDevice):
    """
    File device for sending a wav file to the server. The full wav header
    will be sent to the server and the MIME type "audio/wav" will be used.
    The server is expected to parse the header to infer the audio encoding
    details.

    This device implementation will raise an error if a valid wav header
    cannot be parsed.
    """
    def __init__(self, audio_file=None, **kwargs):
        start_pos = audio_file.tell()
        super().__init__(audio_file, **kwargs)
        if self.audio_file.header is None:
            raise ValueError('File does not contain a valid wav header.')
        audio_file.seek(start_pos)

    def audio_type(self):
        return 'audio/wav'
