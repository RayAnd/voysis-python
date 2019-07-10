from unittest.mock import patch

import pytest
from assertpy import assert_that

from voysis.client.http_client import HTTPClient
from voysis.client.ws_client import WSClient
from voysis.cmd.vtc import client_factory
from voysis.cmd.vtc import device_factory
import voysis.cmd.vtc as vtc

def test_client_factory():
    client = client_factory('wss://loocalhost/websocketapi')
    assert_that(client).is_not_none().is_instance_of(WSClient)
    client = client_factory('https://localhost')
    assert_that(client).is_not_none().is_instance_of(HTTPClient)
    with pytest.raises(ValueError):
        client_factory('ftp://localhost:21')


@patch('voysis.cmd.vtc.MicDevice')
def test_device_factory_emits_mic_device(mic_device_mock):
    vtc._INPUT_DEVICES['mic'] = mic_device_mock
    device = device_factory(record='mic', chunk_size=2048)
    assert_that(device).is_not_none()
    mic_device_mock.assert_called()


def test_device_factory_raises_exception_on_unsupported_device():
    with pytest.raises(KeyError):
        device_factory(record='array', chunk_size=2048)


@patch('voysis.cmd.vtc.RawFileDevice')
def test_device_factory_emits_raw_file_device(raw_device_mock):
    device = device_factory(send='audio.wav', raw=True, chunk_size=2048)
    assert_that(device).is_not_none()
    raw_device_mock.assert_called()


@patch('voysis.cmd.vtc.WavFileDevice')
def test_device_factory_emits_wav_file_device(wav_file_mock):
    device = device_factory(send='audio.wav', raw=False, chunk_size=2048)
    assert_that(device).is_not_none()
    wav_file_mock.assert_called()
