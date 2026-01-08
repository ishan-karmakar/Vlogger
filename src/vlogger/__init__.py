from vlogger import nt4, wpilog, hoot
import logging
import urllib.parse

SOURCES = [
    hoot.Hoot,
    wpilog.WPILog,
    nt4.NetworkTables4
]

def get_source(ident: str, listeners: list, **kwargs):
    url = urllib.parse.urlparse(ident)
    for Source in SOURCES:
        try:
            return Source(url, listeners, **kwargs)
        except TypeError:
            pass

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
