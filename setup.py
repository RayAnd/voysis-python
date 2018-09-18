from setuptools import find_packages
from setuptools import setup
import versioneer

required = [
    "click==6.7",
    "numpy==1.14.5",
    "Cython==0.28.4",
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
    setup_requires=['pytest-runner==4.2', 'flake8==3.5.0'],
    tests_require=['pytest==3.6.3', 'httpretty==0.8.14'],
    entry_points={
        'console_scripts': [
            'voysis-vtc = voysis.cmd.vtc:vtc',
        ],
    },
)
