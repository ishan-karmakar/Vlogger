import abc

class Source(abc.ABC):
    @abc.abstractmethod
    def __init__(self):
        raise NotImplementedError

    @abc.abstractmethod
    def __exit__(self, exception_type, exception_value, exception_traceback):
        raise NotImplementedError
