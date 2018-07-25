import unittest
import json
from unittest.mock import patch, MagicMock, Mock

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

    def assert_text_request_and_call_response(self, request):
        entity = json.loads(request)['entity']
        self.assertEqual(entity['queryType'], 'text')
        self.assertEqual(entity['textQuery']['text'], text_input)
        self.client.on_ws_message(web_socket=None, message=textResponse)

    @patch('voysis.cmd.vtc.input')
    def testSuccessfulTextInputRequest(self, keyboard_input):
        keyboard_input.return_value = text_input
        self.client._websocket_app.send = MagicMock(side_effect=self.assert_text_request_and_call_response)
        obj = {'url': 'wss://test.com', 'record': 'text', 'saved_context': {}, 'voysis_client': self.client}
        CliRunner().invoke(vtc.query, obj=obj, args=['--record', 'text'])
        self.assertEqual(obj['saved_context']['conversationId'], '1')
        self.assertEqual(obj['saved_context']['queryId'], '1')
        self.assertEqual(obj['saved_context']['context']['result'], 'test')


if __name__ == '__main__':
    unittest.main()
