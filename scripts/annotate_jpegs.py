#!/usr/bin/env python3

import sys
import json
import argparse

from pathlib import PurePath
from PIL import Image, ImageDraw

DEFAULT_WORKING_DIR = PurePath('/etc/opt/kerberosio/capture/')
GREEN = (0, 255, 0)

def annotate_jpg(parsed_event, working_directory=DEFAULT_WORKING_DIR):
#    import pdb; pdb.set_trace()
    infile = str(PurePath(working_directory).joinpath(parsed_event['pathToImage']))
    outname = str(PurePath(infile).stem) + ".annotated.jpg"
    outfile = str(PurePath(working_directory).joinpath(outname))

    with Image.open(infile) as im:
        draw = ImageDraw.Draw(im)
        draw.rectangle(parsed_event['regionCoordinates'], fill=None, outline=GREEN, width=2)

        im.save(outfile, "JPEG")


def main():
    parser = argparse.ArgumentParser(description='annotate bounding boxes on jpegs')
    #parser.add_argument('-wd', '--working-directory', default=DEFAULT_WORKING_DIR,
        #help='directory containing all of the input and output files')
    parser.add_argument('input_files', nargs='*',
        help='names of jsonl files to use as input')

    args = parser.parse_args()

    for input_file in args.input_files:
        working_directory = str(PurePath(input_file).parent)


        with open(input_file, 'r') as f:

            for raw_json in f:
                parsed_event = json.loads(raw_json)
                annotate_jpg(parsed_event, working_directory)


if __name__ == "__main__":
    main()
