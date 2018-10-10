import collections
import struct

WaveFileHeader = collections.namedtuple('WaveHeader', ['sample_rate', 'bits_per_sample'])


class WaveFile(object):
    def __init__(self, file):
        self._file = file
        self.header = self._read_header(file)

    @staticmethod
    def _read_header(file):
        file_header = file.read(44)
        # First, lets validate that this is a WAV file
        riff_str, file_size, file_format = struct.unpack('<4sI4s', file_header[:12])
        if b'RIFF' != riff_str or b'WAVE' != file_format:
            raise ValueError("Not a PCM WAV file")
        sample_rate = struct.unpack('<L', file_header[24:28])[0]
        bits_per_sample = struct.unpack('<H', file_header[34:36])[0]
        return WaveFileHeader(sample_rate, bits_per_sample)

    def read(self, size):
        return self._file.read(size)
