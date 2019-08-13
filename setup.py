import sys
from setuptools import find_packages
from setuptools import setup

import versioneer

required = [
    "click==6.7",
    "pyaudio==0.2.11",
    "websocket-client==0.44.0",
    "glog==0.3.1",
    "furl==1.0.1",
    "requests==2.13.0",
    "python-dateutil==2.6.1",
    "tensorflow==1.14.0",
    "sklearn==0.0",
]

needs_pytest_runner = {'pytest', 'test'}.intersection(sys.argv)
pytest_runner = ['pytest-runner==4.2'] if needs_pytest_runner else []

needs_flake8 = {'flake8'}.intersection(sys.argv)
flake8 = ['flake8==3.5.0'] if needs_flake8 else []

setup(
    name='voysis-python',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    author='Voysis',
    author_email='support@voysis.com',
    url='https://github.com/voysis/voysis-python',
    description='Voysis Query API Python Library',
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    packages=find_packages(exclude=['*tests*']),
    license='MIT',
    install_requires=required,
    setup_requires=pytest_runner + flake8,
    tests_require=['pytest==3.6.3', 'httpretty==0.8.14', 'assertpy==0.14'],
    entry_points={
        'console_scripts': [
            'voysis-vtc = voysis.cmd.vtc:vtc',
        ],
    },
)
