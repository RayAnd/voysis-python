
from io import BytesIO

import pytest

from voysis.audio.audio import PCM_FLOAT
from voysis.audio.audio import PCM_SIGNED_INT
from voysis.device.file_device import RawFileDevice
from voysis.device.file_device import WavFileDevice

RAW_16KHZ_NO_HEADER =\
    b'\x00\x32\x00\xbe\x00\x50\x01\xb2\x01\xf8\x01\x3c\x02\x74\x02\xaf'\
    b'\x02\xd7\x02\xba\x02\x35\x02\x89\x01\xa5\x01\x97\x01\x83\x01\xab'\
    b'\x01\x45\x01\xa1\x00\x5f\x00\xda\x00\x6d\x01\xbd\x01\xa7\x01\xb1'\
    b'\x01\x9e\x01\xcd\x01\x24\x02\x11\x02\xba\x01\x8c\x01\xac\x01\x24'\
    b'\x02\x92\x02\xe9\x02\x4e\x03\x5a\x03\xc8\x03\x1d\x04\xf4\x03\x81'\
    b'\x03\x3f\x03\xf3\x02\x5e\x02\x24\x02\x2b\x02\x8c\x01\x52\x01\x92'\
    b'\x01\x94\x01\xd4\x01\x37\x02\x56\x02\x74\x02\xc5\x02\x47\x03\x07'
WAV_44K1HZ =\
    b'\x52\x49\x46\x46\x32\x80\x32\x00\x57\x41\x56\x45\x66\x6d\x74\x20'\
    b'\x12\x00\x00\x00\x03\x00\x01\x00\x44\xac\x00\x00\x10\xb1\x02\x00'\
    b'\x04\x00\x20\x00\x00\x00\x66\x61\x63\x74\x04\x00\x00\x00\x00\xa0'\
    b'\x0c\x00\x64\x61\x74\x61\x00\x80\x32\x00\x00\x00\x4a\xbb\x00\x00'\
    b'\xd4\xbb\x00\x00\x36\xbb\x00\x00\xa0\xbb\x00\x00\x28\xba\x00\x00'\
    b'\x44\x3b\x00\x00\xbe\x3b\x00\x00\x0e\x3b\x00\x00\x0e\x3b\x00\x00'\
    b'\x6e\x3b\x00\x00\x8a\x3b\x00\x00\xc2\x3b\x00\x00\x44\x3b\x00\x00'\
    b'\xb0\x39\x00\x00\x9e\x3b\x00\x00\xb0\x39\x00\x00\x98\x3a\x00\x00'\
    b'\x9a\x3b\x00\x00\x97\x3b\x00\x00\x0a\xbb\x00\x00\xa0\xb9\x00\x00'\
    b'\x80\x38\x00\x00\x99\xbb\x00\x00\xc5\xbb\x00\x00\x9d\xbb\x00\x00'\
    b'\x58\xba\x00\x00\x50\xbb\x00\x00\x22\xbb\x00\x00\x0e\xbb\x00\x00'\
    b'\xa6\x3b\x00\x00\x50\x3a\x00\x00\x30\x3b\x00\x00\x3c\x3b\x00\x00'\
    b'\x4c\x3b\x00\x00\xa4\x3b\x00\x00\xa0\x3b\x00\x00\xd2\x3b'


def test_raw_file_reads_from_start_of_file_with_default_audio_params():
    src = BytesIO(RAW_16KHZ_NO_HEADER)
    device = RawFileDevice(src)
    assert device.audio_file.header is None
    assert device.encoding == PCM_SIGNED_INT
    assert device.sample_rate == 16000
    assert device.bits_per_sample == 16
    assert device.channels == 1
    assert device.big_endian is False
    result = b''
    device.start_recording()
    for chunk in device.generate_frames():
        result += chunk
    device.stop_recording()
    assert result == RAW_16KHZ_NO_HEADER


def test_raw_file_device_parses_and_skips_wav_header_when_present():
    src = BytesIO(WAV_44K1HZ)
    device = RawFileDevice(src)
    assert device.audio_file.header is not None
    assert device.audio_file.header.encoding == PCM_FLOAT
    assert device.audio_file.header.sample_rate == 44100
    assert device.audio_file.header.bits_per_sample == 32
    assert device.audio_file.header.channels == 1
    assert device.audio_file.header.big_endian is False
    assert device.encoding == PCM_FLOAT
    assert device.sample_rate == 44100
    assert device.bits_per_sample == 32
    assert device.channels == 1
    assert device.big_endian is False
    result = b''
    device.start_recording()
    for chunk in device.generate_frames():
        result += chunk
    device.stop_recording()
    assert result == WAV_44K1HZ[58:]


def test_wav_file_device_parses_header_and_includes_header_in_reads():
    src = BytesIO(WAV_44K1HZ)
    device = WavFileDevice(src)
    assert device.audio_file.header is not None
    assert device.audio_file.header.encoding == PCM_FLOAT
    assert device.audio_file.header.sample_rate == 44100
    assert device.audio_file.header.bits_per_sample == 32
    assert device.audio_file.header.channels == 1
    assert device.audio_file.header.big_endian is False
    result = b''
    device.start_recording()
    for chunk in device.generate_frames():
        result += chunk
    device.stop_recording()
    assert result == WAV_44K1HZ


def test_exception_is_raised_by_wav_device_on_invalid_wav_file():
    with pytest.raises(ValueError):
        WavFileDevice(BytesIO(RAW_16KHZ_NO_HEADER))
