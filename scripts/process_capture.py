#!/usr/bin/env python3

import sys
import json
import argparse

from pathlib import PurePath
from PIL import Image, ImageDraw

DEFAULT_WORKING_DIR = PurePath('/etc/opt/kerberosio/capture/')
GREEN = (0, 255, 0)

def write_event_jsonl(parsed_event, working_directory=DEFAULT_WORKING_DIR):

    event_name = PurePath(parsed_event['pathToVideo']).stem

    event_jsonl_file = str(PurePath(working_directory).joinpath(event_name + '.jsonl'))
    with open(event_jsonl_file, 'a+') as single_event_log:
        single_event_log.write(json.dumps(parsed_event, sort_keys=True))
        single_event_log.write("\n")

    single_event_log.close()

def annotate_jpg(parsed_event, working_directory=DEFAULT_WORKING_DIR):
    infile = str(PurePath(working_directory).joinpath(parsed_event['pathToImage']))
    outname = str(PurePath(infile).stem) + ".annotated.jpg"
    outfile = str(PurePath(working_directory).joinpath(outname))

    with Image.open(infile) as im:
        draw = ImageDraw.Draw(im)
        draw.rectangle(parsed_event['regionCoordinates'], fill=None, outline=GREEN, width=2)

        im.save(outfile, "JPEG")


def process_line(raw_json_line, args, write_jsonl=True):
    parsed_event = json.loads(raw_json_line)
    if args.annotate:
        annotate_jpg(parsed_event, args.working_directory) 
    if write_jsonl:
        write_event_jsonl(parsed_event, args.working_directory) 

def main():
    parser = argparse.ArgumentParser(description='Process Kerberos.io events')
    parser.add_argument('-wd', '--working-directory', default=DEFAULT_WORKING_DIR,
        help='directory containing all of the input and output files')
    parser.add_argument('-f', '--input_file', type=argparse.FileType('r'),
        help='Take input from provided filename[s]')
    parser.add_argument('-a', '--annotate', action='store_true',
        help='Draw boxes in *.jpg files, if present')
    parser.add_argument('raw_json', nargs='*',
        help='Single line of JSON')

    args = parser.parse_args()

    if args.input_file:
        with open(str(args.input_file.name), 'r') as f:
            for raw_json in f:
                process_line(raw_json, args, write_jsonl=False)
    else:
        process_line(args.raw_json[0], args, write_jsonl=True)


if __name__ == "__main__":
    main()
