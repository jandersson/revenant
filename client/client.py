from client.login import login
from select import select
import sys

game_connection = login()
while True:
    fds, _, _ = select([game_connection.get_socket(), sys.stdin], [], [])
    for fd in fds:
        if fd == game_connection.get_socket():
            data = game_connection.read_very_eager()
            data = data.decode('ASCII')
            prn = []
            for line in data.split('\n'):
                prn.append(line)
            sys.stdout.write('\n'.join(prn))
            sys.stdout.flush()
        if fd == sys.stdin:
            data = input()
            print(f'> {data}')
            game_connection.write((data + '\n').encode('ASCII'))

