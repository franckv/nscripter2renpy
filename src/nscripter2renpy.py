import sys
import logging
from optparse import OptionParser

from parser import Parser, Translator

if __name__ == '__main__':
    logging.basicConfig(
        level = logging.DEBUG,
        format="[%(levelname)-8s] %(asctime)s %(module)s:%(lineno)d %(message)s",
        datefmt="%H:%M:%S",
        filename = '/tmp/pygmail.log',
        filemode = 'w'
    )

    logging.debug('Start')

    usage = 'Usage: %prog COMMAND [ARGS]'
    parser = OptionParser(usage)
    parser.add_option('-f', dest='filename', help='input filename')

    (options, args) = parser.parse_args()

    if options.filename is None:
        print("filename is missing\n")
        parser.print_help()
        exit(-1)

    parser = Parser()
    input = open(options.filename, 'r', encoding='sjis')

    parser.tokenize(input.read())

    input.close()

    translator = Translator(parser, sys.stdout)

    translator.translate()

