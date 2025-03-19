# FRC Vlogger
## What is this?
Vlogger is a generic library that provides an abstraction over the various kinds of files and live sources that are used in FRC.  
This package is developed and used by FRC Valor 6800 for post match analysis.

## Supported Sources
- [x] [WPILog](https://github.com/wpilibsuite/allwpilib/blob/main/wpiutil/doc/datalog.adoc) (supports structs and protobufs)
- [x] [NetworkTables4](https://github.com/wpilibsuite/allwpilib/blob/main/ntcore/doc/networktables4.adoc) (supports structs and protobufs)
- [x] [CTRE Hoot](https://v6.docs.ctr-electronics.com/en/latest/docs/api-reference/api-usage/signal-logging.html) (file format does not support custom types)
- [ ] DSLog/DSEvents, unlikely to be added soon
- [ ] Phoenix Diagnostic Server

## Motivation
Clients usually just care about the "meat" of the source (that is, the field name, the value, and the timestamp). It usually does not matter to the client where the data came from (i.e. the logic is the same whether it is from a live source or from a log file), and this means that every source should be exposed in a single API that should be a drop in replacement.  
Additionally, there is no ready to use package in Python to parse WPILog files or connect to NetworkTables4 servers.  
This package was heavily inspired by [AdvantageScope](https://github.com/Mechanical-Advantage/AdvantageScope)'s [dataSources](https://github.com/Mechanical-Advantage/AdvantageScope/tree/main/src/hub/dataSources) folder code.

## API Structure
Each source is initialized with:
- A reference to the "connection"
    - For historical logs (i.e. from a log file), this will usually be the path of the log file
    - For live sources (i.e. connecting to a server), this will usually be the hostname of the target machine
- A list of regexes to match the regexes against. This was a design choice made to improve performance by only parsing fields that are going to be used. While not recommended, a regex of `""` can be used to match all fields.
- Any additional arguments that are required for that specific source. This may be for additional configuration or outside executables (the hoot source uses this) to properly parse the file

## Examples
### Initializing a generic source
If the file/connection source is not known, it is recommended to use the `get_source` function to iterate through the sources and performing validation on each.
```python
import vlogger

# "" regex matches with anything, i.e. any field
with vlogger.get_source("my_log.wpilog", [""]) as source:
    for field in source:
        print(field)
```

### Initializing a specific source
If the file/connection source is known, it may be faster and more readable to explicitly initialize the specific source. This example uses the Hoot source, which requires a reference to the [owlet](https://docs.ctr-electronics.com/cli-tools.html) executable (if not found in `PATH`).
```python
from vlogger.sources.wpilog import Hoot

with Hoot("my_log.hoot", ["^MyTargetFields$"], owlet="../my-owlet") as hoot:
    for field in hoot:
        print(field)
```

### Merging sources
Vlogger has the ability to merge multiple sources into one iterable that will be parsed in chronological order. While it has been tested, keep in mind that some sources such as WPILog and even NT4 have been found to itself be store/give data in a non-chronological order. While it has a very low error rate, it is still something to keep in mind when using this feature.
```python
import vlogger

with vlogger.get_source("my_log.wpilog", [""]) as wpilog, \
     vlogger.get_source("my_log.hoot", [""]) as hoot:
    for field in vlogger.merge_sources(wpilog, hoot):
        print(field)
```

## Notes
Vlogger uses the `logging` library internally to log information about the sources, but by design does not configure the logger at all. This means that program that uses Vlogger has the responsibility of setting up the logger.

## Contributing
Contributions are always welcome, especially tasks like adding new sources or fixing bugs. If you are making a big change, please create an issue beforehand to come up with a plan before finishing the code.