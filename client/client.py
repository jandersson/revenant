import logging
import re
from select import select
import sys
from threading import Thread

from login import simu_login

def write_handler(connection):
    write_data = input()
    print(f'> {write_data}')
    connection.write((write_data + '\n').encode('ASCII'))


def write_handler_win32(game_connection):
    while True:
        write_handler(game_connection)

def strip_xml(line):
    if line.startswith('<resource picture'):
        re.sub('<resource picture=.+>', '', line)
    return line

def read_handler(connection):
    read_data = connection.read_very_eager().decode('ASCII')
    buff = []
    for line in read_data.split('\n'):
        if line.startswith(('<component', '<prompt')):
            # TODO: Process XML here
            continue
        buff.append(line)
    sys.stdout.write('\n'.join(buff))
    sys.stdout.flush()


def read_handler_win32(game_connection):
    while True:
        read_handler(game_connection)


def naive_reactor():
    logging.basicConfig()
    log = logging.getLogger('naive_reactor')
    try:
        game_connection = simu_login()
    except Exception as error:
        log.error('Could not establish a connection :(')
        log.error(error)
        sys.exit(1)

    if sys.platform != 'win32':
        while True:
            ## Does not work in Windows! Select cannot operate on non socket objects in Windows (sys.stdin)
            fds, _, _ = select([game_connection.get_socket(), sys.stdin], [], [])
            for fd in fds:
                if fd == game_connection.get_socket():
                    read_handler(game_connection)
                if fd == sys.stdin:
                    write_handler(game_connection)
    else:
        # Windows workaround
        Thread(target=read_handler_win32, args=(game_connection, )).start()
        Thread(target=write_handler_win32, args=(game_connection, )).start()


if __name__ == '__main__':
    naive_reactor()
