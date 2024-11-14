from vlogger.listeners import Listener
import logging
logger = logging.getLogger(__name__)

class StatorCurrentListener(Listener):
    def __init__(self, threshold: int, *fields):
        self.target_fields = fields

    def __call__(self, name: str, timestamp: int, data):
        t = type(data)
        if t != int and t != float:
            logger.warning(f"Encountered unexpected type {t} from {name}")
            raise ValueError
        if not name in self.states:
            self.states[name] = [None, 0, 0]
        if data >= self.threshold and not self.states[name][0]:
            self.states[name][0] = timestamp
        elif data < self.threshold and self.states[name][0]:
            self.states[name][1] += timestamp - self.states[name][0]
            self.states[name][2] += 1
            self.states[name][0] = None

    def eof(self):
        for name, state in self.states.items():
            logger.info(f'"{name}" exceeded {self.threshold} amps {state[2]} times for a total of {state[1] / 1_000} milliseconds')