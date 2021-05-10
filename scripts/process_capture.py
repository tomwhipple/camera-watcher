#!/usr/bin/env python3

import sys
import json

from pathlib import PurePath

EVENT_LOG_FILE = '/etc/opt/kerberosio/capture/video_event_log.txt'
EVENT_LOG_DIR = PurePath(EVENT_LOG_FILE).parent

def main():
    capture_data = sys.argv[1:]

    with open(EVENT_LOG_FILE, 'a+') as event_log:
        event_log.write(str(capture_data))
        event_log.write("\n")

    event_log.close()
    
    parsed_event = json.loads(capture_data[0])

    event_name = PurePath(parsed_event['pathToVideo']).stem
    event_jsonl_file = str(EVENT_LOG_DIR.joinpath(event_name + '.jsonl'))
    with open(event_jsonl_file, 'a+') as single_event_log:
        single_event_log.write(json.dumps(parsed_event, sort_keys=True))
        single_event_log.write("\n")

    single_event_log.close()

if __name__ == "__main__":
    main()
