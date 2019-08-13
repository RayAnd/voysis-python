import os
import sys
import threading
import time
import wave
from collections import deque
from select import select

import glog as log
import pyaudio

from voysis.device.device import Device


class MicDevice(Device):
    def __init__(self, **kwargs):
        Device.__init__(self, **kwargs)
        self.pyaudio_instance = pyaudio.PyAudio()
        self.queue = deque(maxlen=20000)
        self.processed_audio = deque(maxlen=0)
        self.quit_event = threading.Event()
        self.channels = kwargs.get('channels', 1)
        self.sample_rate = kwargs.get('sample_rate')
        if self.sample_rate is None:
            dev_info = self.pyaudio_instance.get_default_input_device_info()
            self.sample_rate = int(dev_info['defaultSampleRate'])
        else:
            self.sample_rate = int(self.sample_rate)
        encoding = kwargs.get('encoding')
        if encoding is None or encoding == 'signed-int':
            self.encoding = pyaudio.paInt16
        elif encoding == 'float':
            self.encoding = pyaudio.paFloat32
        else:
            raise ValueError('Unsupported encoding: ' + str(encoding))
        self.big_endian = kwargs.get('big_endian', False)
        self.device_index = None
        self.wakeword_detected = False
        self._saved_audio = []

    def _callback(self, in_data, frame_count, time_info, status):
        self.queue.append(in_data)
        return None, pyaudio.paContinue

    def stream(self, client, recording_stopper):
        input("Press ENTER to start recording, then speak your query")
        query = None
        self.start_recording()
        recording_stopper.started()
        try:
            def keyboard_stop():
                print("Press ENTER to stop recording (or wait for VAD)")
                while self.is_recording():
                    res = select([sys.stdin], [], [], 1)
                    for sel in res[0]:
                        if sel == sys.stdin:
                            recording_stopper.stop_recording('user_stop')
                            # Consume the input used to stop the recording, so it does not trigger starting again.
                            input()

            keyboard_thread = threading.Thread(target=keyboard_stop)
            keyboard_thread.daemon = True
            keyboard_thread.start()
            query = client.stream_audio(self.generate_frames(), notification_handler=recording_stopper.stop_recording,
                                        audio_type=self.audio_type())
            recording_stopper.stop_recording(None)

        except ValueError:
            pass
        return query

    def stream_with_wakeword(self, client, recording_stopper, wakeword_detector):
        print("Say 'Hey Voysis' to activate.")
        query = None
        self.start_recording()
        recording_stopper.started()
        try:
            def keyboard_stop():
                print("Press ENTER to stop recording.")
                while self.is_recording():
                    res = select([sys.stdin], [], [], 1)
                    for sel in res[0]:
                        if sel == sys.stdin:
                            recording_stopper.stop_recording('user_stop')
                            # Consume the input used to stop the recording, so it does not trigger starting again.
                            input()

            keyboard_thread = threading.Thread(target=keyboard_stop)
            keyboard_thread.daemon = True
            keyboard_thread.start()
            self.wakeword_detected = wakeword_detector.stream_audio(self.generate_frames())
            if self.wakeword_detected:
                print("Wakeword detected.")
                query = client.stream_audio(
                    self.generate_frames(),
                    notification_handler=recording_stopper.stop_recording,
                    audio_type=self.audio_type(),
                )
                recording_stopper.stop_recording(None)
        except ValueError:
            pass
        return query

    def test_wakeword(self, recording_stopper, wakeword_detector):
        wakeword_indices = []
        self.start_recording()
        recording_stopper.started()
        try:
            def keyboard_stop():
                print("Press ENTER to stop recording.")
                while self.is_recording():
                    res = select([sys.stdin], [], [], 1)
                    for sel in res[0]:
                        if sel == sys.stdin:
                            recording_stopper.stop_recording('user_stop')

            keyboard_thread = threading.Thread(target=keyboard_stop)
            keyboard_thread.daemon = True
            keyboard_thread.start()
            wakeword_indices = wakeword_detector.test_wakeword(self.generate_frames())
        except ValueError:
            pass
        except RuntimeError as e:
            print(str(e))
        return wakeword_indices

    def start_recording(self):
        encoding = '32-bit float' if self.encoding == pyaudio.paFloat32 else '16-bit signed integer'
        log.info('Recording %s channels at %sHz using encoding %s', self.channels, self.sample_rate, encoding)
        self._stream = self.pyaudio_instance.open(
            input=True,
            start=False,
            format=self.encoding,
            channels=self.channels,
            rate=self.sample_rate,
            frames_per_buffer=self.chunk_size,
            stream_callback=self._callback,
            input_device_index=self.device_index
        )
        self.quit_event.clear()
        self.queue.clear()
        self._stream.start_stream()

    def stop_recording(self):
        saved_audio_dir_name = "saved_audio"
        self._stream.stop_stream()
        if not os.path.exists(saved_audio_dir_name):
            os.makedirs(saved_audio_dir_name)
        output = wave.open(f"{saved_audio_dir_name}/{time.time()}.wav", 'wb')
        output.setparams((self.channels, 2, self.sample_rate, 0, 'NONE', 'not compressed'))
        output.writeframes(b''.join(self._saved_audio))
        self.quit_event.set()

    def is_recording(self):
        return not(self.quit_event.is_set())

    def generate_frames(self):
        self.quit_event.clear()
        try:
            while not self.quit_event.is_set():
                try:
                    if self.wakeword_detected and self.processed_audio:
                        frames = self.processed_audio.popleft()
                    else:
                        frames = self.queue.popleft()
                        if frames:
                            self._saved_audio.append(frames)
                    if not frames:
                        break
                    if not self.wakeword_detected:
                        self.processed_audio.append(frames)
                    yield frames
                except IndexError:
                    pass
        except StopIteration:
            self._stream.close()
            self.pyaudio_instance.terminate()
            raise
        raise StopIteration()

    def audio_type(self):
        encoding = 'float' if self.encoding == pyaudio.paFloat32 else 'signed-int'
        bits = pyaudio.get_sample_size(self.encoding) * 8
        big_endian = 'true' if self.big_endian else 'false'
        return f'audio/pcm;encoding={encoding};bits={bits};rate={self.sample_rate}' \
               f';channels={self.channels};big-endian={big_endian}'
