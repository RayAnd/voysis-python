
import re
import sys
try:
    from voysis import __version__
except ImportError:
    __version__ = '0.0.1'


class UserAgent:

    def __init__(self, user_agent_app=None):
        self.__user_agent = 'VoysisTestClient/{version} Python/{py.major}.{py.minor}.{py.micro}'.format(
            version=__version__,
            py=sys.version_info
        )
        if user_agent_app:
            self.add_user_agent_app(user_agent_app)

    def get(self):
        return self.__str__()

    def __str__(self):
        return self.__user_agent

    def add_user_agent_app(self, user_agent_app):
        """
        Add an application identifier to the user agent string.
        :param user_agent_app: The application identifier to add. Must
                               match the structure "AppName/version"
        :return: This user agent instance
        """
        if not(re.match("^[-a-zA-Z0-9_.]+/[a-zA-Z0-9][-a-zA-Z0-9_.]*$", user_agent_app)):
            raise ValueError("Invalid user agent app value " + user_agent_app)
        else:
            self.__user_agent = self.__user_agent + " " + user_agent_app
        return self
