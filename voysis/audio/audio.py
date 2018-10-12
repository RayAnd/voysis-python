import collections
import struct

AudioFileHeader = collections.namedtuple('AudioFileHeader', ['sample_rate', 'bits_per_sample'])


class AudioFile(object):
    def __init__(self, file):
        self._file = file
        self.header = self._read_header(file)

    @staticmethod
    def _read_header(file):
        riff_chunk = file.read(12)
        riff_str, file_size, file_format = struct.unpack('<4sI4s', riff_chunk[:12])
        # First, lets validate if this is a WAV file
        if b'RIFF' == riff_str and b'WAVE' == file_format:
            fmt_chunk = file.read(24)
            format_code = struct.unpack('<H', fmt_chunk[8:10])[0]
            sample_rate = struct.unpack('<L', fmt_chunk[12:16])[0]
            bits_per_sample = struct.unpack('<H', fmt_chunk[22:24])[0]
            if format_code == 3:
                # For IEEE float format, there may be header extensions
                extension_size = struct.unpack('<H', file.read(2))[0]
                file.read(extension_size)
            elif format_code != 1:
                raise ValueError(f'Unsupported format code {format_code}')
            # Read the chunks until we get to the "data" chunk
            while True:
                chunk_id, chunk_size = struct.unpack("<4sI", file.read(8))
                if b'data' == chunk_id:
                    break
                else:
                    # Read past this chunk
                    file.read(chunk_size)
        else:
            # Default to 16KHz, 16bit.
            sample_rate = 16000
            bits_per_sample = 16
            file.seek(0)
        return AudioFileHeader(sample_rate, bits_per_sample)

    def read(self, size):
        return self._file.read(size)
