import json
import threading

import websocket

from voysis.client import client as client
from voysis.client.client_version_info import ClientVersionInfo


class WSClient(client.Client):

    def __init__(self, url: str, client_info: ClientVersionInfo = None, timeout: int = 15):
        client.Client.__init__(self, url, client_info, timeout)
        self._websocket_app = None
        self._web_socket_thread = None
        self._next_request_id = 1
        self._complete_reason = None
        self._notification_handler = None
        self._event = threading.Event()
        self._completed_query = None
        self._response_futures = dict()
        self._error = None

    def send_audio(self, frames_generator):
        for frame in frames_generator:
            if self._complete_reason:
                break
            self._websocket_app.send(frame, websocket.ABNF.OPCODE_BINARY)
        if not self._complete_reason:
            self.finalise_audio()

    def send_request(self, uri, request_entity=None, extra_headers=None, call_on_complete=None, method='POST'):
        request_id = self._next_request_id
        self._next_request_id = self._next_request_id + 1
        body = {
            'type': 'request',
            'requestId': request_id,
            'method': method,
            'restUri': uri,
            'entity': request_entity
        }
        headers = self.create_common_headers()
        if extra_headers:
            headers.update(extra_headers)
        body['headers'] = headers
        response_future = client.ResponseFuture(call_on_complete=call_on_complete)
        self._response_futures[str(request_id)] = response_future
        self._websocket_app.send(json.dumps(body))
        return response_future

    def finalise_audio(self):
        '''
        When VAD is not encountered this has to be send to notify server that all audio has been sent
        '''
        self._websocket_app.send([4], websocket.ABNF.OPCODE_BINARY)

    def on_ws_message(self, web_socket, message):
        json_msg = json.loads(message)
        if 'response' == json_msg['type']:
            if int(json_msg['responseCode']) > 299:
                self._error = client.ClientError(
                    "Request {requestId} failed with status code {responseCode}: {responseMessage}".format(**json_msg)
                )
            try:
                future = self._response_futures.pop(json_msg['requestId'])
                future.set(
                    json_msg['responseCode'],
                    response_message=json_msg['responseMessage'],
                    response_entity=json_msg['entity']
                )
                if json_msg['entity']['queryType'] == "text":
                    self._completed_query = json_msg['entity']
                    self._update_state()
            except KeyError:
                pass
        elif 'notification' == json_msg['type']:
            notification_type = json_msg['notificationType']
            if 'query_complete' == notification_type:
                self._completed_query = json_msg['entity']
            self._update_state(notification_type, 'vad_stop' != notification_type)

    def on_ws_error(self, web_socket, error):
        try:
            self._complete_reason = 'error'
            self._error = error
            web_socket.close()
        except websocket.WebSocketException:
            self._update_state()

    def on_ws_open(self, web_socket):
        self._event.set()

    def on_ws_close(self, web_socket):
        self._update_state()

    def connect(self):
        """
        Connect the WebSocket. This method blocks until the socket is
        successfully connected. If the socket does not connect within
        the client's timeout, ClientError is raised.
        :return: bool True if the connection was successful
        """
        if not self._websocket_app:
            self._event.clear()
            self._websocket_app = websocket.WebSocketApp(
                self._url,
                on_message=self.on_ws_message,
                on_error=self.on_ws_error,
                on_open=self.on_ws_open,
                on_close=self.on_ws_close
            )
            self._web_socket_thread = WebSocketThread(self._websocket_app, check_hostname=self.check_hostname)
            self._web_socket_thread.start()
            connected = self._wait_for_event('WebSocket connection')
        else:
            connected = self._websocket_app.sock.connected
        return connected

    def close(self):
        """
        Close the WebSocket. Blocks until the WebSocket is closed and internal
        client resources are cleaned up.
        :return: None
        """
        self._websocket_app.close()
        self._web_socket_thread.join()
        self._web_socket_thread = None
        self._websocket_app = None

    def stream_audio(self, frames_generator, notification_handler=None, audio_type=None):
        return self.execute_request(frames_generator, notification_handler,
                                    self._create_audio_query_entity(audio_type))

    def send_text(self, text):
        return self.execute_request(entity=self._create_text_query_entity(text))

    def send_feedback(self, query_id, rating=None, description=None, durations=None):
        self.connect()
        return super(WSClient, self).send_feedback(query_id, rating, description, durations)

    def execute_request(self, frames_generator=None, notification_handler=None, entity=None):
        try:
            self._complete_reason = None
            self._error = None
            self._notification_handler = notification_handler
            self.connect()
            self.refresh_app_token()
            # self._event.clear()
            self.send_request('/queries', entity, call_on_complete=self._update_current_conversation)
            # self._wait_for_event('query creation')
            self._event.clear()
            if frames_generator is not None:
                self.send_audio(frames_generator)
            self._wait_for_event('query completion')
            completed_query = self._completed_query
            self._completed_query = None
            if completed_query:
                self._update_current_context(completed_query)
                return completed_query
            else:
                raise client.ClientError("Query failed {}".format(self._complete_reason))
        except OSError as error:
            raise client.ClientError(error.strerror)
        except websocket.WebSocketConnectionClosedException as error:
            # This exception typically happens when we try to continue
            # streaming after the server side has shut down the socket
            # due to an error condition.
            if self._error:
                raise self._error
            else:
                raise error
        except websocket.WebSocketException as error:
            raise client.ClientError(str(error))
        finally:
            self._notification_handler = None

    def _wait_for_event(self, message):
        if not self._event.wait(self.timeout):
            raise client.ClientError("Timed out waiting on " + message)
        if self._error:
            raise self._error

    def _update_state(self, complete_reason=None, response_ready=True):
        if complete_reason:
            self._complete_reason = complete_reason
        notification_handler = self._notification_handler
        if notification_handler:
            notification_handler(self._complete_reason)
        if response_ready:
            self._event.set()

    def _update_current_conversation(self, response_future):
        if response_future.response_code == 201:
            self.current_conversation_id = response_future.get_entity()['conversationId']
        # self._event.set()


class WebSocketThread(threading.Thread):
    def __init__(self, web_socket_app, **kwargs):
        '''
        Initialise the WebSocketThread.
        :param web_socket_app: The application to run on this thread.
        :param kwargs: +check_hostname+: (boolean) enable or disable checking the hostname on TLS connections.
        '''
        threading.Thread.__init__(self)
        self._web_socket_app = web_socket_app
        self._ssl_opts = {
            'check_hostname': kwargs.get('check_hostname', True)
        }
        self.running_event = threading.Event()

    def run(self):
        self.running_event.set()
        self.running_event = None
        self._web_socket_app.run_forever(sslopt=self._ssl_opts)
