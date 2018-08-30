__all__ = ['__version__', 'client', 'cmd', 'device']

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
