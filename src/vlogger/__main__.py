from argparse import ArgumentParser
import logging
from vlogger.sources import SourceType, nt4, wpilog, hoot
from vlogger.listeners import auto_align_error, stator_current

SOURCES = [
    nt4.NetworkTables4,
    wpilog.WPILog,
    hoot.Hoot
]

LISTENERS = [
    auto_align_error.AutoAlignError(
        r"^NT:/LiveWindow/BaseSubsystem/SwerveDrive/Align: Rotation Align$",
        r"^NT:/LiveWindow/BaseSubsystem/SwerveDrive/Target Angle$",
        r"^NT:/LiveWindow/BaseSubsystem/SwerveDrive/Align: Y Goal Align$",
        r"^NT:/?LiveWindow/BaseSubsystem/SwerveDrive/Actual Calculated Pose$",
        r"^NT:/LiveWindow/BaseSubsystem/SwerveDrive/Y Distance$",
        r"^NT:/LiveWindow/BaseSubsystem/Scorer/State: Scoring$",
        r"^NT:/LiveWindow/BaseSubsystem/Scorer/State: Gamepiece$",
    )
    # stator_current.StatorCurrentListener(
    #     60,
    #     r"^NT:/LiveWindow/PhoenixController/ID 2/Stator Current$",
    #     r"^NT:/LiveWindow/PhoenixController/ID 4/Stator Current$",
    #     r"^NT:/LiveWindow/PhoenixController/ID 6/Stator Current$",
    #     r"^NT:/LiveWindow/PhoenixController/ID 8/Stator Current$"
    # )
]

def run():
    parser = ArgumentParser()
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("-f", "--file", action="append", help="The filename to parse")
    source_group.add_argument("-r", "--robot", help="The robot IP")
    parser.add_argument("-v", "--verbose", help="Enable verbose logging", action="store_true")
    parser.add_argument("--owlet", help="Path to owlet executable for HOOT -> WPILOG conversion")
    args = parser.parse_args()

    logging.basicConfig(format="[%(levelname)s] %(name)s: %(message)s")
    if args.verbose:
        logging.root.setLevel(logging.NOTSET)
    else:
        logging.root.setLevel(logging.INFO)

    # Map of regex -> listeners
    regex_listeners = {}
    for listener in LISTENERS:
        for field in listener.target_regexes:
            if not field in regex_listeners:
                regex_listeners[field] = { listener }
            else:
                regex_listeners[field].add(listener)

    # Right now only first source is being used
    sources = []
    if args.file:
        for file in args.file:
            org = len(sources)
            for Source in SOURCES:
                # Annoying hack to get around enums across modules not working
                # https://github.com/python/cpython/issues/74730
                if Source.SOURCE_TYPE.value != SourceType.HISTORICAL.value:
                    continue
                try:
                    sources.append(Source(regex_listeners, file, args))
                    break
                except ValueError:
                    pass
            if len(sources) == org:
                logging.warning(f"Could not find valid Source for {file}")
    elif args.robot:
        for Source in SOURCES:
            if Source.SOURCE_TYPE != SourceType.LIVE:
                continue
            try:
                sources.append(Source(regex_listeners, args.robot, args))
                break
            except ValueError:
                pass

    matched_regexes = set()
    sources_queue = { iter(source): None for source in sources }
    # Work around to delete from dict while iterating
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
        min_it = min(sources_queue, key=lambda v: sources_queue.get(v)[3])
        regexes, listeners, name, timestamp, data = sources_queue[min_it]
        matched_regexes |= regexes
        for listener in listeners:
            listener(name, timestamp, data)

        try:
            sources_queue[min_it] = next(min_it)
        except StopIteration:
            del sources_queue[min_it]

    for source in sources:
        source.close()

    for listener in LISTENERS:
        listener.eof()

    for regex in regex_listeners.keys():
        if not regex in matched_regexes:
            logging.warning(f"Regex '{regex.pattern}' was never matched")

if __name__ == '__main__':
    run()