#!/usr/bin/env python3

import sys

EVENT_LOG_FILE = '/etc/opt/kerberosio/capture/video_event_log.txt'

def main():
    capture_data = sys.argv[1:]

    with open(EVENT_LOG_FILE, 'a+') as event_log:
        event_log.write(str(capture_data))
        event_log.write("\n")

    event_log.close()
    

if __name__ == "__main__":
    main()
