import abc

class Source(abc.ABC):
    @abc.abstractmethod
    def __init__(self):
        raise NotImplementedError

    @abc.abstractmethod
    def close(self):
        raise NotImplementedError
    
    @abc.abstractmethod
    def __iter__(self):
        raise NotImplementedError
