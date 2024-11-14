import abc, re

class Listener(abc.ABC):
    def __init__(self, **kwargs):
        self.target_regexes = []
        for k, v in kwargs.items():
            pattern = re.compile(v)
            self.__dict__[k] = pattern
            self.target_regexes.append(pattern)

    @abc.abstractmethod
    def __call__(self, timestamp, data):
        raise NotImplementedError
    
    @abc.abstractmethod
    def eof(self):
        raise NotImplementedError