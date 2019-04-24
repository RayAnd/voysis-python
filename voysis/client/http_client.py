import base64
import json

import requests
from furl import furl
from requests import HTTPError
from requests.packages.urllib3.exceptions import HTTPError as UrlLib3HTTPError

from voysis.client import client as client


class HTTPClient(client.Client):

    def __init__(self, url, client_info=None, timeout=15):
        client.Client.__init__(self, url, client_info, timeout)
        self.base_url = furl(url)

    def send_request(self, uri, request_entity=None, extra_headers=None, call_on_complete=None, method='POST'):
        headers = self.create_common_headers()
        if extra_headers:
            headers.update(extra_headers)
        url = self.base_url.copy().add(path=uri)
        req_method = getattr(requests, method.lower())
        response = req_method(
            str(url),
            headers=headers,
            json=request_entity,
            verify=self.check_hostname,
            timeout=self.timeout
        )
        return client.ResponseFuture(
            response_code=response.status_code,
            response_entity=response.json(),
            call_on_complete=call_on_complete
        )

    def stream_audio(self, frames_generator, notification_handler=None, audio_type=None):
        try:
            self.refresh_app_token()
            entity = self._create_audio_query_entity(audio_type)
            headers = self.create_common_headers()
            headers['Content-Type'] = audio_type
            headers['X-Voysis-Entity'] = base64.b64encode(json.dumps(entity).encode("UTF-8"))
            streaming_url = self.base_url.copy().add(path=['queries'])
            response = requests.post(
                str(streaming_url),
                headers=headers,
                stream=True,
                verify=self.check_hostname,
                timeout=self.timeout,
                data=frames_generator
            )
            if response.status_code == 200:
                query = response.json()
                self.current_conversation_id = query['conversationId']
                self._update_current_context(query)
                notification_handler('query_complete')
                return query
            else:
                raise client.ClientError('Request failed with status code {}'.format(response.status_code))
        except OSError as error:
            msg = error.strerror
            if not msg:
                msg = str(error)
            raise client.ClientError(msg)
        except (HTTPError, UrlLib3HTTPError) as error:
            raise client.ClientError(str(error))

    def send_text(self, text):
        self.refresh_app_token()
        return self.send_request('/queries', request_entity=self._create_text_query_entity(text)).get_entity()
