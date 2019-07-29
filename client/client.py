from login import simu_login
import logging
from select import select
import sys


def write_handler(connection):
    write_data = input()
    print(f'> {write_data}')
    connection.write((write_data + '\n').encode('ASCII'))


def read_handler(connection):
    read_data = connection.read_very_eager().decode('ASCII')
    buff = []
    for line in read_data.split('\n'):
        buff.append(line)
    sys.stdout.write('\n'.join(buff))
    sys.stdout.flush()


def naive_reactor():
    logging.basicConfig()
    log = logging.getLogger('naive_reactor')
    try:
        game_connection = simu_login()
    except Exception as error:
        log.error('Could not establish a connection :(')
        log.error(error)
        sys.exit(1)

    while True:
        fds, _, _ = select([game_connection.get_socket(), sys.stdin], [], [])
        for fd in fds:
            if fd == game_connection.get_socket():
                read_handler(game_connection)
            if fd == sys.stdin:
                write_handler(game_connection)


if __name__ == '__main__':
    naive_reactor()
