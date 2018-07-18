import json
import os
import sys
import threading
import traceback
from collections import defaultdict
from select import select
from time import time

import click
import glog as log
from future.builtins import input

from voysis.client.client import ClientError
from voysis.client.http_client import HTTPClient
from voysis.client.ws_client import WSClient
from voysis.device.file_device import FileDevice
from voysis.device.mic_array.mic_array import MicArrayDevice
from voysis.device.mic_device import MicDevice
from voysis.version import __version__

MICROPHONE = 'mic'
MICROPHONE_ARRAY = 'mic_ar'
MICROPHONE_DUMMY = 'mic_file'


class RecordingStopper(object):
    """
    A class that can be used to stop a device recording and save interesting event information.
    """
    def __init__(self, device, query_start, durations):
        """
        Create a new RecordingStopper instance.
        :param device: The device that will be stopped.
        :param query_start: The timestamp of the start of the query.
        :param durations: A dict that will be populated with relevant durations.
        """
        self._device = device
        self._query_start = int(query_start * 1000)
        self._durations = durations
        self._mappings = {
            'vad_stop': 'vad',
            'user_stop': 'userStop',
            'query_complete': 'complete'
        }

    def stop_recording(self, reason):
        was_recording = self._device.is_recording()
        self._device.stop_recording()
        if was_recording:
            print("Recording stopped (%s), waiting for response.." % reason)
        if reason:
            event_timestamp = int(time() * 1000) - self._query_start
            duration_name = self._mappings.get(reason, reason)
            self._durations[duration_name] = event_timestamp


def valid_file(parser, arg):
    if not os.path.isfile(arg):
        parser.error("The file %s does not exist!" % arg)
    else:
        return open(arg, 'rb') # return an open file handle


def valid_folder(parser, arg):
    if not os.path.isdir(arg):
        parser.error("The folder %s does not exist!" % arg)
    else:
        return arg


def valid_mic(parser, arg):
    if arg not in [MICROPHONE, MICROPHONE_ARRAY]:
        parser.error('Microphone set to {}. Accepted values: {p1}, {p2}'.format(arg, p1=MICROPHONE, p2=MICROPHONE_ARRAY))
    else:
        return arg


def valid_rating(parser, arg):
    if arg < 1 or arg > 5:
        parser.error('Rating set to {}. Accepted values: 1-5'.format(arg))
    else:
        return arg


def client_factory(url):
    if url.startswith('ws://') or url.startswith('wss://'):
        client = WSClient(url)
    elif url.startswith('http://') or url.startswith('https://'):
        client = HTTPClient(url)
    else:
        raise ValueError('No client for protocol in URL %s' % url)
    return client


def device_factory(record, **kwargs):
    if record == MICROPHONE_DUMMY:
        device = FileDevice(**kwargs)

    if record == MICROPHONE_ARRAY:
        # TODO make Microphone array stream concatenate all the channels to only one
        raise ValueError('')
        device = None
        # device = MicArrayDevice(client)

    if record == MICROPHONE:
        device = MicDevice(**kwargs)

    return device


def stream_mic(client, device, durations):
    print("Ready to capture your voice query")
    input("Press ENTER to start recording")
    query = None
    query_start = time()
    device.start_recording()
    try:
        recording_stopper = RecordingStopper(device, query_start, durations)

        def keyboard_stop():
            print("Press ENTER to stop recording (or wait for VAD)")
            while device.is_recording():
                res = select([sys.stdin], [], [], 1)
                for sel in res[0]:
                    if sel == sys.stdin:
                        recording_stopper.stop_recording('user_stop')

        keyboard_thread = threading.Thread(target=keyboard_stop)
        keyboard_thread.daemon = True
        keyboard_thread.start()
        query = client.stream_audio(device.generate_frames(), notification_handler=recording_stopper.stop_recording, 
                                    audio_type=device.audio_type())
        recording_stopper.stop_recording(None)
    except ValueError:
        pass
    return query


def stream_file(client, device, durations):
    recording_stopper = RecordingStopper(device, time(), durations)
    device.start_recording()
    query = client.stream_audio(device.generate_frames(), notification_handler=recording_stopper.stop_recording, 
                                audio_type=device.audio_type())
    recording_stopper.stop_recording(None)
    return query


def stream(voysis_client, file=None, record=None, **kwargs):
    if file is not None:
        record = MICROPHONE_DUMMY
    device = device_factory(record, **kwargs)
    if isinstance(device, MicDevice) or isinstance(device, MicArrayDevice):
        streamer = stream_mic
    if isinstance(device, FileDevice):
        log.info('Streaming file {}'.format(file.name))
        device.wav_file = file
        streamer = stream_file
    durations = {}
    result = streamer(voysis_client, device, durations)
    print('Durations: ' + (json.dumps(durations)))
    voysis_client.send_feedback(result['id'], durations=durations)
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
    '--record', '-r', type=click.Choice([MICROPHONE, MICROPHONE_ARRAY, MICROPHONE_DUMMY]), default=MICROPHONE,
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
        if not kwargs.get('batch', None):
            response, query_id, conversation_id = stream(
                voysis_client, kwargs.get('send', None), kwargs['record'], chunk_size=kwargs['chunk_size']
            )
            json.dump(response, sys.stdout, indent=4)
            saved_context['conversationId'] = conversation_id
            saved_context['queryId'] = query_id
            saved_context['context'] = voysis_client.current_context
            write_context(obj['url'], saved_context, 'context.json')
        else:
            for root, dirs, files in os.walk(kwargs['batch']):
                log.info('Streaming files from folder {}'.format(kwargs['batch']))
                for file in files:
                    if file.endswith('.wav'):
                        file_path = os.path.join(kwargs['batch'], file)
                        response, query_id, conversation_id = stream(voysis_client, open(file_path, 'rb'))
                        json.dump(response, sys.stdout, indent=4)
    except ClientError as client_error:
        log.error(client_error.message)
    except Exception as e:
        log.info(traceback.format_exc())
        log.info('Error: {err}'.format(err=e))


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
