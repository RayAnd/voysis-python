from setuptools import find_packages
from setuptools import setup
from voysis.version import __version__

required = [
    "numpy==1.14.0",
    "Cython==0.24",
    "configParser==3.5.0",
    "pyaudio==0.2.11",
    "pyusb==1.0.2",
    "websocket-client==0.44.0",
    "glog==0.3.1",
    "furl==1.0.1",
    "requests==2.13.0",
    "six==1.11.0",
    "future==0.16.0",
    "python-dateutil==2.6.1",
]

setup(
    name='voysis-python',
    version=__version__,
    author='Voysis',
    author_email='support@voysis.com',
    url='https://github.com/voysis/voysis-python',
    description='Voysis Query API Python Library',
    long_description=open('README.md').read(),
    packages=find_packages(exclude=['*tests*']),
    license='MIT',
    install_requires=required,
    tests_require=['httpretty==0.8.14'],
    entry_points={
        'console_scripts': [
            'voysis-vtc = voysis.cmd.vtc:main',
            'record-ma = voysis.cmd.record_ma:main',
        ],
    },
)
