import io

from voysis.audio.audio import AudioFile
from voysis.audio.audio import PCM_FLOAT
from voysis.audio.audio import PCM_SIGNED_INT


def test_16khz_file():
    audio_file = AudioFile(io.BytesIO(b'\x52\x49\x46\x46\x22\xe2\x01\x00\x57\x41\x56\x45\x66\x6d\x74\x20\x10\x00'
                                      b'\x00\x00\x01\x00\x01\x00\x80\x3e\x00\x00\x00\x7d\x00\x00\x02\x00\x10\x00'
                                      b'\x64\x61\x74\x61\xfe\xe1\x01\x00\x74\x65\x73\x74'))
    assert audio_file.header.encoding == PCM_SIGNED_INT
    assert audio_file.header.bits_per_sample == 16
    assert audio_file.header.sample_rate == 16000
    assert audio_file.header.channels == 1
    assert audio_file.header.big_endian is False
    assert audio_file.read(4) == b'test'


def test_48khz_file():
    audio_file = AudioFile(io.BytesIO(b'\x52\x49\x46\x46\x32\x00\x0a\x00\x57\x41\x56\x45\x66\x6d\x74\x20\x12\x00'
                                      b'\x00\x00\x03\x00\x01\x00\x80\xbb\x00\x00\x00\xee\x02\x00\x04\x00\x20\x00'
                                      b'\x00\x00\x66\x61\x63\x74\x04\x00\x00\x00\x01\x62\x02\x00\x64\x61\x74\x61'
                                      b'\x04\x88\x09\x00\x74\x65\x73\x74'))
    assert audio_file.header.encoding == PCM_FLOAT
    assert audio_file.header.bits_per_sample == 32
    assert audio_file.header.sample_rate == 48000
    assert audio_file.header.channels == 1
    assert audio_file.header.big_endian is False
    assert audio_file.read(4) == b'test'


def test_48khz_big_endian_file():
    audio_file = AudioFile(io.BytesIO(b'\x52\x49\x46\x58\x00\x0a\x00\x32\x57\x41\x56\x45\x66\x6d\x74\x20\x00\x00'
                                      b'\x00\x12\x00\x03\x00\x01\x00\x00\xbb\x80\x00\x02\xee\x00\x00\x04\x00\x20'
                                      b'\x00\x00\x66\x61\x63\x74\x00\x00\x00\x04\x00\x02\x62\x01\x64\x61\x74\x61'
                                      b'\x00\x09\x88\x04\x74\x65\x73\x74'))
    assert audio_file.header.encoding == PCM_FLOAT
    assert audio_file.header.bits_per_sample == 32
    assert audio_file.header.sample_rate == 48000
    assert audio_file.header.channels == 1
    assert audio_file.header.big_endian is True
    assert audio_file.read(4) == b'test'


def test_raw_audio():
    audio_file = AudioFile(io.BytesIO(b'\x0f\x0e\x0d\x0c\x0b\x0a\x09\x08\x07\x06\x05\x04\x03\x02\x01\x00\x00\x00'
                                      b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                                      b'\x00\x00\x00\x00\x00\x00\x00\x00'))
    assert audio_file.header is None
    assert audio_file.read(16) == b'\x0f\x0e\x0d\x0c\x0b\x0a\x09\x08\x07\x06\x05\x04\x03\x02\x01\x00'
