#!/usr/bin/env python3

import sys
import json

from pathlib import PurePath

EVENT_LOG_DIR = PurePath('/etc/opt/kerberosio/capture/')

def main():
    capture_data = sys.argv[1:]

    parsed_event = json.loads(capture_data[0])

    event_name = PurePath(parsed_event['pathToVideo']).stem
    event_jsonl_file = str(EVENT_LOG_DIR.joinpath(event_name + '.jsonl'))
    with open(event_jsonl_file, 'a+') as single_event_log:
        single_event_log.write(json.dumps(parsed_event, sort_keys=True))
        single_event_log.write("\n")

    single_event_log.close()

if __name__ == "__main__":
    main()
