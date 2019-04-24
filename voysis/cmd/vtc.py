import json
import os
import sys
import traceback
from collections import defaultdict
from time import time

import click
import glog as log

from voysis import __version__
from voysis.audio.audio import PCM_FLOAT
from voysis.audio.audio import PCM_SIGNED_INT
from voysis.client.client import Client, QDT_ACCEPTANCE_TEST, QDT_UAT, QDT_DEV, QDT_PROBE, QDT_LIVE
from voysis.client.client import ClientError
from voysis.client.client_version_info import ClientVersionInfo
from voysis.client.http_client import HTTPClient
from voysis.client.ws_client import WSClient
from voysis.device.device import Device
from voysis.device.file_device import RawFileDevice
from voysis.device.file_device import WavFileDevice
from voysis.device.mic_device import MicDevice

# Valid input sources. The keys of this dict are the valid values that can
# be supplied to the --record option. The values are the handler classes
# for that device type.
_INPUT_DEVICES = {
    'mic': MicDevice,
    'default': 'mic'
}

_vtc_version_info = ClientVersionInfo(app_name='voysis-vtc', app_version=__version__)


class RecordingStopper(object):
    """
    A class that can be used to stop a device recording and save interesting event information.
    """

    def __init__(self, device, durations):
        """
        Create a new RecordingStopper instance.
        :param device: The device that will be stopped.
        :param durations: A dict that will be populated with relevant durations.
        """
        self._device = device
        self._query_start = None
        self._recording_stopped = None
        self._durations = durations
        self._mappings = {
            'vad_stop': 'vad',
            'user_stop': 'userStop',
            'query_complete': 'complete'
        }

    def started(self):
        """
        Method that should be called by devices to indicate that recording/streaming has commenced.
        :return: The query start time, in seconds since the epoch.
        """
        self._query_start = int(time() * 1000)
        return self._query_start

    def stop_recording(self, reason):
        was_recording = self._device.is_recording()
        self._device.stop_recording()
        if was_recording:
            print("Recording stopped (%s), waiting for response.." % reason)
            self._recording_stopped = int(time() * 1000)
        if reason:
            event_timestamp = int(time() * 1000) - self._query_start
            duration_name = self._mappings.get(reason, reason)
            self._durations[duration_name] = event_timestamp


def valid_file(parser, arg):
    if not os.path.isfile(arg):
        parser.error("The file %s does not exist!" % arg)
    else:
        return open(arg, 'rb')  # return an open file handle


def valid_folder(parser, arg):
    if not os.path.isdir(arg):
        parser.error("The folder %s does not exist!" % arg)
    else:
        return arg


def valid_rating(parser, arg):
    if arg < 1 or arg > 5:
        parser.error('Rating set to {}. Accepted values: 1-5'.format(arg))
    else:
        return arg


def client_factory(url):
    if url.startswith('ws://') or url.startswith('wss://'):
        client = WSClient(url, client_info=_vtc_version_info)
    elif url.startswith('http://') or url.startswith('https://'):
        client = HTTPClient(url, client_info=_vtc_version_info)
    else:
        raise ValueError('No client for protocol in URL %s' % url)
    return client


def device_factory(**kwargs):
    device_init_args = {
        'encoding': kwargs.get('encoding'),
        'sample_rate': kwargs.get('sample_rate'),
        'big_endian': kwargs.get('big_endian'),
        'chunk_size': kwargs['chunk_size']
    }
    file_to_send = kwargs.get('send')
    if file_to_send is None:
        input_source = kwargs.get('record')
        device = _INPUT_DEVICES[input_source](**device_init_args)
    else:
        send_raw = kwargs['raw']
        if send_raw:
            device = RawFileDevice(file_to_send, **device_init_args)
        else:
            device = WavFileDevice(file_to_send, **device_init_args)
    return device


def stream(voysis_client: Client, audio_device: Device):
    durations = {}
    recording_stopper = RecordingStopper(audio_device, durations)
    result = audio_device.stream(voysis_client, recording_stopper)
    print('Durations: ' + (json.dumps(durations)))
    voysis_client.send_feedback(result['id'], durations=durations)
    return result, result['id'], result['conversationId']


def send_text(voysis_client, text):
    result = voysis_client.send_text(text)
    return result, result['id'], result['conversationId']


def send_feedback(voysis_client, query_id, rating, description):
    feedback_result = voysis_client.send_feedback(query_id, rating, description)
    return json.dumps(feedback_result, indent=4, sort_keys=True)


def read_context(saved_context_file):
    ctx = defaultdict(lambda: dict(conversationId=None, context=dict()))
    if os.path.isfile(saved_context_file):
        with open(saved_context_file, 'r') as f:
            loaded = json.load(f)
            ctx.update(loaded)
    return ctx


def write_context(url, context, saved_context_file):
    full_context = read_context(saved_context_file)
    full_context[url] = context
    with open(saved_context_file, 'w') as f:
        json.dump(full_context, f, indent=4)


@click.group()
@click.option(
    '--url', '-u', type=str, envvar='VTC_URL', required=True,
    help='The URL of the Query API service. Can be provided in the environment using VTC_URL.'
)
@click.option(
    '--audio-profile-id', type=str, envvar='VTC_AUDIO_PROFILE_ID',
    help='Set your audio profile ID. Uses a random value if not specified. Can be provided in the environment'
         ' using VTC_AUDIO_PROFILE_ID.'
)
@click.option(
    '--auth-token', '-t', type=str, envvar='VTC_AUTH_TOKEN',
    help='Provide the client refresh token used to obtain a session token. Can be provided in the environment'
         ' using VTC_AUTH_TOKEN.'
)
@click.option(
    '--check-hostname/--no-check-hostname', is_flag=True, default=True,
    help='For TLS, enable or disable hostname verification. Enabled by default.'
)
@click.option(
    '--timeout', envvar='VTC_TIMEOUT', default=20,
    help='The time (in seconds) that the client will wait for a response from the service.'
         ' Can be provided in the environment using VTC_TIMEOUT'
)
@click.version_option(version=__version__)
@click.pass_context
def vtc(context, **kwargs):
    saved_context = read_context('context.json')
    url = kwargs['url']
    voysis_client = client_factory(url)
    if kwargs['audio_profile_id'] is not None:
        voysis_client.audio_profile_id = kwargs['audio_profile_id']
    voysis_client.auth_token = kwargs['auth_token']
    voysis_client.check_hostname = kwargs['check_hostname']
    voysis_client.timeout = kwargs['timeout']
    context.obj = {
        'url': url,
        'voysis_client': voysis_client,
        'saved_context': saved_context.get(url, {})
    }


@vtc.resultcallback()
@click.pass_obj
def close_client(obj, results, **kwargs):
    print('closing..')
    obj['voysis_client'].close()


@vtc.command(help='Send audio query and get response.')
@click.option(
    '--send', '-s', type=click.File('rb'), help='Send wav file'
)
@click.option(
    '--raw/--wav', is_flag=True, default=True,
    help='Send the supplied file as raw samples with the audio/pcm MIME type. If the file is a wav file, the'
         'audio parameters will be read from the header and the header will be skipped. To send a full wav file,'
         ' including its header, and use the audio/wav MIME type, use the --wav option.'
)
@click.option(
    '--send-text', type=str, help='Send text', default=False
)
@click.option(
    '--record', '-r', type=click.Choice(_INPUT_DEVICES.keys()), default=_INPUT_DEVICES['default'],
    help='Record from mic and send audio stream.'
)
@click.option(
    '--batch', '-b', type=click.Path(file_okay=False, allow_dash=False), help='Sends all the wav files from a folder'
)
@click.option(
    '--use-conversation', '-c', is_flag=True, envvar='VTC_USE_CONVERSATION', default=False,
    help='Create a new query in a conversation, using the conversation ID from saved context. Can be provided'
         ' in the environment using VTC_USE_CONVERSATION=1.'
)
@click.option(
    '--locale', type=str, envvar='VTC_LOCALE', default='en-US',
    help='Specify the locale of created queries. Defaults to en-US. Can be provided in the environment using'
         ' VTC_LOCALE.'
)
@click.option(
    '--ignore-vad', is_flag=True, envvar='VTC_IGNORE_VAD', default=False,
    help='Ignore Voice Activity Detection for queries. Can be provided in the environment using VTC_IGNORE_VAD=1.'
)
@click.option(
    '--use-context', '-x', is_flag=True, envvar='VTC_USE_CONTEXT', default=False,
    help='Send saved context along with the query (omit to use a blank context). Can be provided in the'
         ' environment using VTC_USE_CONTEXT=1.'
)
@click.option(
    '--chunk-size', envvar='VTC_CHUNK_SIZE', default=1024,
    help='Set the chunk/buffer size used by audio data devices. Can be provided in the environment using'
         ' VTC_CHUNK_SIZE..'
)
@click.option(
    '--sample-rate', envvar='VTC_SAMPLE_RATE', type=click.Choice(['16000', '44100', '48000']),
    help='Set the sample rate to use when recording audio from the microphone. If not specified, the default'
         ' system sample rate will be used. Can be provided in the environment using VTC_SAMPLE_RATE'
)
@click.option(
    '--encoding', envvar='VTC_ENCODING', type=click.Choice([PCM_SIGNED_INT, PCM_FLOAT]),
    help='Specify the encoding to send. Can be provided in the environment using VTC_ENCODING'
)
@click.option(
    '--big-endian/--little-endian', is_flag=True, default=False,
    help='Specify the endianness of samples. This defaults to little-endian and must be explicitly overridden'
         ' if the hardware is generating big-endian samples.'
)
@click.option(
    '--query-data-type', envvar='VTC_QUERY_DATA_TYPE',
    type=click.Choice([QDT_LIVE, QDT_PROBE, QDT_DEV, QDT_UAT, QDT_ACCEPTANCE_TEST]),
    default=QDT_DEV, help='Specify the query data type. Defaults to DEV. Can be provided in the'
                          ' environment using VTC_QUERY_DATA_TYPE'
)
@click.pass_obj
def query(obj, **kwargs):
    try:
        saved_context = obj['saved_context']
        voysis_client = obj['voysis_client']
        if kwargs['use_conversation']:
            voysis_client.current_conversation_id = saved_context['conversationId']
        if kwargs['use_context']:
            voysis_client.current_context = saved_context['context'].copy()
        voysis_client.locale = kwargs['locale']
        voysis_client.ignore_vad = kwargs['ignore_vad']
        voysis_client.query_data_type = kwargs['query_data_type']

        if kwargs['send_text']:
            text = kwargs['send_text']
            execute_request(obj, saved_context, voysis_client, send_text(voysis_client, text))
        elif not kwargs.get('batch', None):
            audio_device = device_factory(**kwargs)
            execute_request(
                obj,
                saved_context,
                voysis_client,
                stream(
                    voysis_client,
                    audio_device,
                )
            )
        else:
            for root, dirs, files in os.walk(kwargs['batch']):
                log.info('Streaming files from folder {}'.format(kwargs['batch']))
                device_class = RawFileDevice if kwargs['raw'] else WavFileDevice
                device_init_args = {'chunk_size': kwargs.get('chunk_size')}
                for file in files:
                    if file.endswith('.wav'):
                        file_path = os.path.join(kwargs['batch'], file)
                        with open(file_path, 'rb') as wav_file:
                            audio_device = device_class(wav_file, **device_init_args)
                            response, query_id, conversation_id = stream(voysis_client, audio_device)
                            json.dump(response, sys.stdout, indent=4)
    except ClientError as client_error:
        log.error(client_error.message)
    except Exception as e:
        log.info(traceback.format_exc())
        log.info('Error: {err}'.format(err=e))


def execute_request(obj, saved_context, voysis_client, call):
    response, query_id, conversation_id = call
    json.dump(response, sys.stdout, indent=4)
    saved_context['conversationId'] = conversation_id
    saved_context['queryId'] = query_id
    saved_context['context'] = voysis_client.current_context
    write_context(obj['url'], saved_context, 'context.json')


@vtc.command(help='Send feedback for a particular query.')
@click.option('--query-id', help='Set the query ID for sending feedback. Read from saved context if not provided here.')
@click.option('--rating', help='Set the rating (int 1-5) for feedback. Required for feedback request.')
@click.option('--description', help='Set a text description to go with the rating in the feedback request. Optional.')
@click.pass_obj
def feedback(obj, **kwargs):
    query_id = kwargs.get('query_id', None)
    if not query_id:
        query_id = obj['saved_context']['queryId']
    if not query_id:
        print("You must specify the ID of a query to provide feedback for.")
        raise SystemExit(1)
    print("Sending feedback for query ID {}".format(query_id))
    response = send_feedback(obj['voysis_client'], query_id, kwargs['rating'], kwargs.get('description', None))
    print(response)


if __name__ == "__main__":
    try:
        sys.exit(vtc())
    except KeyboardInterrupt:
        print("DONE")
