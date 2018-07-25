import websocket
import unittest
import pytest
import json
from unittest.mock import MagicMock
from click.testing import CliRunner
from voysis.client.ws_client import WSClient
from voysis.cmd import vtc

textResponse = """{"type":"response","entity":{"id":"1","locale":"en-US","conversationId":"1","queryType":"text",
"textQuery":{"text":""},"context":{"result":"test"},"intent":"","reply":{"text":""},"entities":{"products":[]},
"userId":""},"requestId":"1","responseCode":201,"responseMessage":"Created"} """
text_input = 'text input'


@pytest.fixture
def client_fixture():
    client = WSClient(url="wss://test.com")
    client._websocket_app = MagicMock(return_value=None)
    client._event = MagicMock(return_value=None)
    return client


def assert_text_request_and_call_response(request, client):
    entity = json.loads(request)['entity']
    assert entity['queryType'] == 'text'
    assert entity['textQuery']['text'] == text_input
    client.on_ws_message(web_socket=None, message=textResponse)


def call_on_ws_error(client):
    client.on_ws_error(web_socket=MagicMock(return_value=None), error=websocket.WebSocketException)


def test_error_text_input_request(client_fixture):
    client_fixture._websocket_app.send = MagicMock(side_effect=lambda _: call_on_ws_error(client_fixture))
    obj = {'url': 'wss://test.com', 'record': 'text', 'saved_context': {}, 'voysis_client': client_fixture}
    CliRunner().invoke(vtc.query, obj=obj, args=['--send-text', text_input])
    assert client_fixture._complete_reason == 'error'


def test_success_text_input_request(client_fixture):
    client_fixture._websocket_app.send = MagicMock(
        side_effect=lambda x: assert_text_request_and_call_response(x, client_fixture))
    obj = {'url': 'wss://test.com', 'record': 'text', 'saved_context': {}, 'voysis_client': client_fixture}
    CliRunner().invoke(vtc.query, obj=obj, args=['--send-text', text_input])
    assert obj['saved_context']['conversationId'] == '1'
    assert obj['saved_context']['queryId'] == '1'
    assert obj['saved_context']['context']['result'] == 'test'


if __name__ == '__main__':
    unittest.main()
