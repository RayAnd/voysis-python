import collections
import struct

AudioFileHeader = collections.namedtuple('AudioFileHeader', ['sample_rate', 'bits_per_sample'])


class AudioFile(object):
    def __init__(self, file):
        self._file = file
        self.header = self._read_header(file)

    @staticmethod
    def _read_header(file):
        file_header = file.read(44)
        # First, lets validate if this is a WAV file
        riff_str, file_size, file_format = struct.unpack('<4sI4s', file_header[:12])
        if b'RIFF' == riff_str and b'WAVE' == file_format:
            sample_rate = struct.unpack('<L', file_header[24:28])[0]
            bits_per_sample = struct.unpack('<H', file_header[34:36])[0]
        else:
            # Default to 16KHz, 16bit.
            sample_rate = 16000
            bits_per_sample = 16
            file.seek(0)
        return AudioFileHeader(sample_rate, bits_per_sample)

    def read(self, size):
        return self._file.read(size)
