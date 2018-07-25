import unittest
import json
from unittest.mock import patch, MagicMock, Mock

import websocket
from click.testing import CliRunner

from voysis.client.ws_client import WSClient
from voysis.cmd import vtc

textResponse = """{"type":"response","entity":{"id":"1","locale":"en-US","conversationId":"1","queryType":"text",
"textQuery":{"text":""},"context":{"result":"test"},"intent":"","reply":{"text":""},"entities":{"products":[]},
"userId":""},"requestId":"1","responseCode":201,"responseMessage":"Created"} """
text_input = 'text input'


class VTCWebSocketTest(unittest.TestCase):

    def setUp(self):
        self.client = WSClient(url="wss://test.com")
        self.client._websocket_app = MagicMock(return_value=None)
        self.client._event = MagicMock(return_value=None)
        self.obj = {'url': 'wss://test.com', 'record': 'text', 'saved_context': {}, 'voysis_client': self.client}

    def assert_text_request_and_call_response(self, request):
        entity = json.loads(request)['entity']
        self.assertEqual(entity['queryType'], 'text')
        self.assertEqual(entity['textQuery']['text'], text_input)
        self.client.on_ws_message(web_socket=None, message=textResponse)

    def call_on_ws_error(self, request):
        self.client.on_ws_error(web_socket=MagicMock(return_value=None), error=websocket.WebSocketException)

    @patch('voysis.cmd.vtc.input')
    def testErrorTextInputRequest(self, keyboard_input):
        keyboard_input.return_value = text_input
        self.client._websocket_app.send = MagicMock(side_effect=self.call_on_ws_error)
        CliRunner().invoke(vtc.query, obj=self.obj, args=['--send-text', text_input])
        self.assertEqual(self.client._complete_reason, 'error')

    @patch('voysis.cmd.vtc.input')
    def testSuccessfulTextInputRequest(self, keyboard_input):
        keyboard_input.return_value = text_input
        self.client._websocket_app.send = MagicMock(side_effect=self.assert_text_request_and_call_response)
        CliRunner().invoke(vtc.query, obj=self.obj, args=['--send-text', text_input])
        self.assertEqual(self.obj['saved_context']['conversationId'], '1')
        self.assertEqual(self.obj['saved_context']['queryId'], '1')
        self.assertEqual(self.obj['saved_context']['context']['result'], 'test')


if __name__ == '__main__':
    unittest.main()
