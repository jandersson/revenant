import argparse
import logging
import re
from select import select
import sys
from threading import Thread
import xml.etree.ElementTree as ET

from login import simu_login


def is_windows():
    return sys.platform == 'win32'


class Client:
    """A basic DR client"""
    def __init__(self):
        # TODO: Real logging
        logging.basicConfig()
        self.log = logging.getLogger()

        try:
            self.connection = simu_login()
        except Exception as error:
            self.log.error('Could not establish a connection :(')
            self.log.error(error)
            sys.exit(1)

        self.reactor()

    def reactor(self):
        """A very basic implementation of handling input/output"""
        connection = self.connection
        if is_windows():
            # Windows workaround for select issue
            def read_loop():
                while True:
                    self.read()

            def write_loop():
                while True:
                    self.write()

            Thread(target=read_loop).start()
            Thread(target=write_loop).start()
        else:
            while True:
                # select cannot operate on non socket objects in Windows (sys.stdin)
                fds, _, _ = select([connection.get_socket(), sys.stdin], [], [])
                for fd in fds:
                    if fd == connection.get_socket():
                        self.read()
                    if fd == sys.stdin:
                        self.write()

    def write(self):
        write_data = input()
        print(f'> {write_data}')
        self.connection.write((write_data + '\n').encode('ASCII'))

    def read(self):
        read_data = self.connection.read_very_eager().decode('ASCII')
        buff = []
        for line in read_data.split('\n'):

            line = xml_handler(line)
            if line:
                buff.append(line)
        sys.stdout.write('\n'.join(buff))
        sys.stdout.flush()


def xml_handler(line):
    # Handle room xml
    # Just remove it for now
    line = re.sub('<resource picture=.+/>', '', line)
    line = re.sub('<style id=.+/>', '', line)
    if line.startswith('Obvious paths:'):
        line = re.sub('</?d>', '', line)
    if line.startswith('<compass'):
        line = re.sub('<compass>.+</compass>', '', line)
    if line.startswith('<prompt'):
        xml = re.search('<prompt.+</prompt>', line)

        def xml_prompt(_xml, _line):
            if not _xml:
                return _line
            try:
                _line = re.sub('<prompt.+</prompt>', ET.fromstring(xml.group(0)).text, _line)
            except ET.ParseError as error:
                print(f"Parse Error! {error}")
            return _line
        line = xml_prompt(xml, line)
    return line


if __name__ == '__main__':
    argparser = argparse.ArgumentParser(description='A mud client')
    # TODO: Implement
    argparser.add_argument('--character-file',
                           default=None,
                           help='Login using credentials stored in this file')
    # TODO: Implement
    argparser.add_argument('--test',
                           action='store_true',
                           default=False,
                           help="Use a mock connection instead of connecting to the game")
    args = argparser.parse_args()
    Client()
