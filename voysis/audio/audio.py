import struct

PCM_SIGNED_INT = 'signed-int'
PCM_FLOAT = 'float'

_RIFF = 0x52494646
_RIFX = 0x52494658
_WAVE = 0x57415645
_FMT_ = 0x666d7420
_FACT = 0x66616374
_DATA = 0x64617461


class _InsufficientDataError(RuntimeError):
    pass


class AudioFileHeader(object):
    def __init__(
            self,
            encoding: str='signed-int',
            sample_rate: int=16000,
            bits_per_sample: int=16,
            channels: int=1,
            big_endian: bool=False
    ):
        self.encoding = encoding
        self.sample_rate = sample_rate
        self.bits_per_sample = bits_per_sample
        self.channels = channels
        self.big_endian = big_endian


class AudioFile(object):
    def __init__(self, file):
        self._file = file
        start_pos = file.tell()
        self.header = self._read_header(file)
        if self.header is None:
            file.seek(start_pos)

    @staticmethod
    def _read_header(file):
        try:
            riff_chunk = AudioFile._read_at_least(file, 12)
            riff_id = struct.unpack('>L', riff_chunk[0:4])[0]
            if riff_id not in [_RIFF, _RIFX]:
                return None
            big_endian = False
            if _RIFX == riff_id:
                unsigned_short = '>H'
                unsigned_int = '>L'
                big_endian = True
            else:
                unsigned_short = '<H'
                unsigned_int = '<L'
            file_format = struct.unpack('>L', riff_chunk[8:12])[0]
            if file_format != _WAVE:
                return None
            audio_file_header = None
            while True:
                chunk_id, chunk_len, chunk_data = AudioFile._read_sub_chunk(file, unsigned_int)
                if chunk_id == _FMT_:
                    format_code = struct.unpack(unsigned_short, chunk_data[0:2])[0]
                    channels = struct.unpack(unsigned_short, chunk_data[2:4])[0]
                    sample_rate = struct.unpack(unsigned_int, chunk_data[4:8])[0]
                    bits_per_sample = struct.unpack(unsigned_short, chunk_data[14:16])[0]
                    encoding = PCM_SIGNED_INT
                    if format_code == 3:
                        encoding = PCM_FLOAT
                    elif format_code != 1:
                        raise ValueError(f'Unsupported format code {format_code}')
                    audio_file_header = AudioFileHeader(
                        encoding=encoding,
                        sample_rate=sample_rate,
                        bits_per_sample=bits_per_sample,
                        channels=channels,
                        big_endian=big_endian
                    )
                elif chunk_id == _DATA:
                    break
            if audio_file_header:
                if audio_file_header.channels != 1:
                    raise ValueError(f"Exactly 1 channel is supported, header identifies {channels}")
            return audio_file_header
        except _InsufficientDataError:
            return None

    @staticmethod
    def _read_sub_chunk(file, unsigned_int):
        d = AudioFile._read_at_least(file, 8)
        chunk_id = struct.unpack('>L', d[0:4])[0]
        chunk_len = struct.unpack(unsigned_int, d[4:8])[0]
        if chunk_id != _DATA:
            chunk_data = AudioFile._read_at_least(file, chunk_len)
        else:
            chunk_data = b''
        return chunk_id, chunk_len, chunk_data

    @staticmethod
    def _read_at_least(file, byte_count):
        data = file.read(byte_count)
        if len(data) < byte_count:
            raise _InsufficientDataError()
        return data

    def read(self, size):
        return self._file.read(size)
