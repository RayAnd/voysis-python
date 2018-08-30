[![Build Status](https://travis-ci.org/voysis/voysis-python.svg?branch=master)](https://travis-ci.org/voysis/voysis-python)

# Voysis Python Library

The Voysis Python Library provides a set of classes that allow Python
applications to interact with Voysis Query API endpoints.

A command-line invocation tool is also supplied to provide both an
easy way to interact with the Voysis Query API and a working example
of how to consume the library classes.

## Installation

To install from the PyPI repository, simply run

```
pip3 install --upgrade voysis-python
```

or to install from this source tree, execute

```
python3 setup.py install
```

### Requirements

The Voysis Python library and command line tool require Python 3, with
Python 3.6 being the recommended environment.

`portaudio` is required to operate in a Mac OSX environment. This can
be installed using [Homebrew](https://brew.sh)

```
brew install portaudio 
```

## API Documentation

The full documentation for the Voysis API can be found here:
[Voysis Developer Documentation](https://developers.voysis.com/docs)

## VTC: The Voysis Test Client

This project supplies a command-line testing tool called `voysis-vtc`, which
provides a simple way to test and interact with a Voysis Voice AI.


### Getting Help

After installation, run `voysis-vtc --help` for a summary of the command line
arguments and sub-commands available. Re-running the tool with a sub-command
name and `--help` will give further help for that sub-command:

```
voysis-vtc query --help
```

### Specifying Your Voice AI Endpoint

To execute queries against your Voice AI endpoint, you will need to tell
VTC the URL of your Voice AI. This URL will be supplied to you by Voysis.

To provide it to VTC, use the global `--url` option:

```
voysis-vtc --url wss://test.voysis.io/websocketapi query
```

You can also specify the endpoint URL in your environment so that you
do not have to provide on the command line for each invocation:

```
export VTC_URL=wss://test.voysis.io/websocketapi
```

### Authentication

Your Voice AI endpoint will require an authentication token to be
specified for queries to be successful. The VTC command supports
specifying a valid refresh token using the global `--auth-token` option:

```
voysis-vtc \
    --auth-token=8U7CsQyiK8bqLwGnZUmnmgArbmiR9si50DIrjIHp5soAJ4i7NHB2Gg3IhlIgXYN1 \
    --url=wss://test.voysis.io/websocketapi \
    query
```

You can also provide the refresh token in your environment so that you do not
need to provide it on the command line for each invocation:

```
export VTC_AUTH_TOKEN=8U7CsQyiK8bqLwGnZUmnmgArbmiR9si50DIrjIHp5soAJ4i7NHB2Gg3IhlIgXYN1
```

### Interacting with Your Voice AI

The most direct way of interacting with your Voice AI is by sending a single
query recorded from the microphone.

To record a voice query and send it to the Voice AI, execute

```
voysis-vtc query
```

and follow the on-screen prompts.

### Sending an Audio File

The VTC client can send a file containing audio data rather than recording
from the microphone. Currently only files containing raw samples or a wav
file are supported. In both cases, the audio data _must_ confirm to the
following parameters:

 * 16000Hz 16-bit signed integer single-channel PCM data.

```
voysis-vtc query --send audio_data.wav
```

### Sending Many Audio Files

The VTC client supports sending a batch of audio files sequentially to
a Voice AI endpoint. The path to a directory containing many wav files
should be supplied on the command line:

```
voysis-vtc query --batch /path/to/wav/folder
``` 

### Providing Query Feedback

The Voysis Query API supports providing feedback on the quality of the
results of an audio query. To provide this feedback, use the `feedback`
sub-command:

```
voysis-vtc feedback \
           --query-id dda80ba2-f0fa-421d-8462-2f849bbb30b3 \
           --rating 5 \
           --description="Perfect results"
```

The rating is a simple integer in the range 1 - 5 with 1 representing the
poorest quality and 5 representing the best. Description is a free-form
string that can be used to provide additional information about why the
query results were poor. This information will be stored alongside the
query and can be used by Voysis to improve Voice AIs.
