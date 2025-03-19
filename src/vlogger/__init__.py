from vlogger.sources import Source
from vlogger.sources import nt4, wpilog, hoot
import logging

SOURCES = [
    # Hoot is above 
    hoot.Hoot,
    wpilog.WPILog,
    # Order is very important here, live sources (specifically NT4) should be at the end
    # It is much harder to validate that a live connection is actually the correct source
    # While log files usually have a header or equivalent
    nt4.NetworkTables4
]

def get_source(path: str, listeners: list, **kwargs) -> Source:
    for Source in SOURCES:
        try:
            return Source(path, listeners, **kwargs)
        except Exception as e:
            logging.debug(f"Source {Source.__name__} skipped, encountered error '{e}'")

    # TODO: Find a real built in exception class or create new one SourceNotFound
    raise Exception("Source not found")

def merge_sources(*sources):
    sources_queue = { iter(source): None for source in sources }

    for k in sources_queue.copy().keys():
        try:
            sources_queue[k] = next(k)
        except StopIteration:
            del sources_queue[k]
    
    while len(sources_queue):
        '''
        This is a quick and dirty implementation for chronologically merging the logs,
        but in testing the WPILog + NT4 itself sometimes is not entirely in order (very low error rate but still there),
        so something to keep in mind when processing a large number of fields
        '''
        min_it = min(sources_queue, key=lambda v: sources_queue.get(v)["timestamp"])
        field_data = sources_queue[min_it]
        yield field_data

        try:
            sources_queue[min_it] = next(min_it)
        except StopIteration:
            del sources_queue[min_it]
