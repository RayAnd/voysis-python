import json
import threading
from typing import Any
from typing import Callable
from typing import Mapping
from typing import Union

import glog as log
import websocket

from voysis.client import client as client
from voysis.client.client_version_info import ClientVersionInfo

__all__ = [
    'WSClient',
]


COMPLETE_ERROR = 'error'


class CompletionGate(object):
    """
    A thread synchronization object to track the state of a single query
    execution. A wrapped ``threading.Event`` can be waited to detect the
    final state of the query (both normal completion or an error).
    """
    def __init__(self, notification_handler: Callable = None) -> None:
        """
        Create a new ``CompletionGate`` instance.
        :param notification_handler: A callable that accepts a single string
        parameter. The notification handler will be called for certain events
        in a query's lifecycle. Where a notification message is received from
        the server (such as "vad_stop"), the notification handler will receive
        a corresponding event with the string value of the notification type.
        Other events may also be delivered, most notable being one containing
        the value of the ``COMPLETE_ERROR`` constant indicating that query
        processing has failed due to an error.
        """
        self._event = threading.Event()
        self._notification_handler = notification_handler
        self._reason = None
        self._entity = None

    @property
    def event(self):
        return self._event

    @property
    def reason(self):
        return self._reason

    @property
    def entity(self) -> Union[Mapping[str, Any], client.ClientError]:
        return self._entity

    def check_is_complete(self) -> bool:
        """
        Check if this completion gate indicates that the event is complete.
        Also checks for an error and raises the exception if it is set.
        :return: True if the event is complete, False otherwise.
        """
        if self._reason == COMPLETE_ERROR:
            raise self._entity
        else:
            return self._reason is not None

    def set_error(self, error: Any) -> None:
        """
        Set this completion gate's final status to error. The threading event
        will be set so any threads waiting on the gate's final state will
        be notified. The gate's notification handler, if any, will be called
        with ``COMPLETE_ERROR``.
        :param error: The error to report to the client.
        :return: None
        """
        self._reason = COMPLETE_ERROR
        if isinstance(error, client.ClientError):
            self._entity = error
        else:
            self._entity = client.ClientError(error)
        if self._notification_handler:
            self._notification_handler(self._reason)
        self._event.set()

    def set_complete(self, reason: str, completed_query: Any = None) -> None:
        """
        Set this completion gate's final status to complete. The threading
        event will be set so any threads waiting on the gate's final state
        will be notified. The gate's notification handler, if any, will be
        called with the ``reason``.
        :param reason: The complete reason, typically ``query_complete``
        :param completed_query: The completed query.
        :return: None
        """
        self._reason = reason
        self._entity = completed_query
        if self._notification_handler:
            self._notification_handler(self._reason)
        self._event.set()

    def notify_of_event(self, event_name: str) -> None:
        """
        Deliver a non-completion notification to this gate's notification
        handler, if any. The threading event's state will _not_ be set. If
        there is no notification handler, invoking this is a noop.
        :param event_name: The name of the event to deliver to the notification
        handler.
        :return: None
        """
        if self._notification_handler:
            self._notification_handler(event_name)

    def reset(self, notification_handler: Callable = None) -> None:
        """
        Reset this completion gate, clearing the current notification handler,
        reason, entity and resetting the threading event. A completion gate
        must be reset between the completion of one query and the initiation
        of another.
        :param notification_handler: Set the current notification handler to
        this value, clearing any previous value.
        :return: None
        """
        self._notification_handler = notification_handler
        self._reason = None
        self._entity = None
        self._event.clear()


class WSClient(client.Client):

    def __init__(self, url: str, client_info: ClientVersionInfo = None, timeout: int = 15):
        client.Client.__init__(self, url, client_info, timeout)
        self._websocket_app = None
        self._web_socket_thread = None
        self._next_request_id = 1
        self._notification_handler = None
        self._completion_gate = CompletionGate()
        self._response_futures = dict()

    def send_audio(self, frames_generator):
        for frame in frames_generator:
            if self._completion_gate.check_is_complete():
                break
            self._websocket_app.send(frame, websocket.ABNF.OPCODE_BINARY)
        if not self._completion_gate.check_is_complete():
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
            request_id = json_msg.get('requestId')
            response_code = int(json_msg.get('responseCode', 501))
            response_message = json_msg.get('responseMessage', 'Invalid response from server')
            entity = json_msg.get('entity')
            if response_code > 299:
                self._completion_gate.set_error(
                    f'Request {request_id} failed with status code {response_code}: {response_message}'
                )
            future = self._response_futures.pop(request_id, None)
            if future:
                future.set(
                    response_code,
                    response_message=json_msg['responseMessage'],
                    response_entity=entity,
                )
            if entity and entity.get('queryType') == "text":
                self._completion_gate.set_complete('query_complete', json_msg['entity'])
        elif 'notification' == json_msg['type']:
            notification_type = json_msg['notificationType']
            if 'query_complete' == notification_type:
                self._completion_gate.set_complete(notification_type, json_msg['entity'])
            elif notification_type in ['internal_server_error', 'client_error']:
                self._completion_gate.set_error(json_msg.get('message', 'unidentified error'))
            else:
                self._completion_gate.notify_of_event(notification_type)

    def on_ws_error(self, web_socket, error):
        try:
            web_socket.close()
            self._completion_gate.set_error(error)
        except websocket.WebSocketException:
            self._completion_gate.set_error(error)

    def on_ws_close(self, web_socket):
        log.debug('The WebSocket has been closed.')

    def connect(self):
        """
        Connect the WebSocket. This method blocks until the socket is
        successfully connected. If the socket does not connect within
        the client's timeout, ClientError is raised.
        :return: bool True if the connection was successful
        """
        if not self._websocket_app:
            connected_event = threading.Event()

            def on_ws_open(websocket):
                log.debug('WebSocket is connected.')
                connected_event.set()

            self._websocket_app = websocket.WebSocketApp(
                self._url,
                on_message=self.on_ws_message,
                on_error=self.on_ws_error,
                on_open=on_ws_open,
                on_close=self.on_ws_close
            )
            self._web_socket_thread = WebSocketThread(self._websocket_app, check_hostname=self.check_hostname)
            self._web_socket_thread.start()
            connected = connected_event.wait(self.timeout)
        else:
            connected = self._websocket_app.sock.connected
        return connected

    def close(self):
        """
        Close the WebSocket. Blocks until the WebSocket is closed and internal
        client resources are cleaned up.
        :return: None
        """
        if self._websocket_app:
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
            self._completion_gate.reset(notification_handler=notification_handler)
            self.connect()
            self.refresh_app_token()
            self.send_request('/queries', entity, call_on_complete=self._update_current_conversation)
            self._completion_gate.event.clear()
            if frames_generator is not None:
                self.send_audio(frames_generator)
            if not self._completion_gate.event.wait():
                raise client.ClientError("Timed out waiting on query completion")
            if self._completion_gate.check_is_complete():
                self._update_current_context(self._completion_gate.entity)
                return self._completion_gate.entity
            else:
                raise client.ClientError("Unknown error waiting for query completion")
        except OSError as error:
            raise client.ClientError(error.strerror)
        except websocket.WebSocketConnectionClosedException as error:
            # This exception typically happens when we try to continue
            # streaming after the server side has shut down the socket
            # due to an error condition. Calling check will cause the
            # error set by on_ws_error to be raised, if any.
            self._completion_gate.check_is_complete()
            raise error
        except websocket.WebSocketException as error:
            raise client.ClientError(str(error))
        finally:
            self._completion_gate.reset()

    def _update_current_conversation(self, response_future):
        if response_future.response_code == 201:
            self.current_conversation_id = response_future.get_entity()['conversationId']


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
