import os, sys
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

    usage = 'Usage: %prog dirname'
    optparser = OptionParser(usage)

    (options, args) = optparser.parse_args()

    if len(args) == 0:
        optparser.print_usage()
        sys.exit(-1)

    dirname = args[0]
    if dirname is None:
        dirname = os.getcwd()

    parser = Parser()

    parser.load_images(dirname)

    script = os.path.join(dirname, 'nscript.dat')
    input = open(script, 'rb')
    content = parser.read_script(input)
    input.close()
    content = content.decode('sjis')

    parser.tokenize(content)

    translator = Translator(parser, sys.stdout)

    translator.translate()

