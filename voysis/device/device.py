import abc


class Device(abc.ABC):

    def __init__(self, **kwargs):
        self.chunk_size = kwargs.get('chunk_size', 1024)

    @abc.abstractmethod
    def stream(self, client, recording_stopper):
        pass

    @abc.abstractmethod
    def start_recording(self):
        pass

    @abc.abstractmethod
    def stop_recording(self):
        pass

    @abc.abstractmethod
    def is_recording(self):
        pass

    @abc.abstractmethod
    def generate_frames(self):
        pass

    @abc.abstractmethod
    def audio_type(self):
        pass
