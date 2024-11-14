import abc
from enum import Enum

class SourceType(Enum):
    LIVE = 0
    HISTORICAL = 1

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
