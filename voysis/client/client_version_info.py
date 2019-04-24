
import json
import platform

try:
    from voysis import __version__
except ImportError:
    __version__ = '0.0.1'


class ClientVersionInfo:

    def __init__(self, app_name: str = None, app_version: str = None):
        self._client_version_info = {
            'os': {
                'id': platform.system(),
                'version': platform.release()
            },
            'sdk': {
                'id': 'voysis-python',
                'version': __version__
            },
        }
        if app_name is not None:
            self._client_version_info['app'] = {
                'id': app_name,
                'version': app_version
            }

    def get(self) -> str:
        return self.__str__()

    def __str__(self):
        return json.dumps(self._client_version_info)
