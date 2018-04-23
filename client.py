import struct
import re
import getpass
from telnetlib import Telnet

HOST = 'eaccess.play.net'
PORT = 7900
GAME_CODE = b'DR'
# Protocol Actions - Sending to server (summary only):
# K - Server responses with Key (to encrypt password with)
# The server response, will always be 32 characters, then 0x0a
# A - This action tells the server what user/pass you're dealing with
# M - Asks the server for a list of games
# N - Asks server for game capabilities
# G - Tells the server what game you want, server responds with some details
# C - Asks the server for a list of characters specifically, other stuff included
# L - Tells the server you want to play a character, server responds with connection info
# F - (Unknown) SGE Sends it... Server response: NORMAL
# B - (Unknown) zMUD Sends it... Server response: UNKNOWN
# P - (Unknown) SGE Sends it w/ gamecode.. Server response: ?God knows what?


class LoginError(Exception):
    def __init__(self, message):
        super().__init__(message)


def a_action(client, credentials):
    """Inform the server of the user/pass, return what appears to be a login key?"""
    hashed_password = encrypt_password(credentials['password'], credentials['hashkey'])
    client.write(b'A\t' + credentials['username'] + b'\t' + hashed_password + b'\n')
    a_response = client.read_until(b'\n').decode()
    if 'PASSWORD' in a_response:
        raise LoginError('Bad Password')
    elif 'NORECORD' in a_response:
        raise LoginError('Bad Username')
    elif 'REJECTED' in a_response:
        raise LoginError('Account suspended? Login Rejected')
    elif 'KEY' in a_response:
        key = re.compile(".*\tKEY\t(.+)\t").match(a_response).group(1)
        return key
    else:
        raise LoginError('Something went wrong while trying to log in')


def k_action(client):
    """Sends request for key to encrypt password with"""
    client.write(b'K\n')
    return client.read_until(b'\n')


def g_action(client):
    """Tell the server what game you want"""
    client.write(b'G\t' + GAME_CODE + b'\n')
    return client.read_until(b'\n')


def c_action(client, character_name):
    """Poll server for list of characters, return character code"""
    client.write(b'C\n')
    c_response = client.read_until(b'\n')
    character_code = re.compile("C\t\d\t\d\t\d\t\d\t(.+)\t" + character_name).match(c_response.decode()).group(1)
    return character_code


def l_action(client, character_code):
    """Inform server of which character to play, return the server response with connection info"""
    client.write(b'L\t' + character_code.encode('ASCII') + b'\t' + b'STORM\n')
    l_response = client.read_until(b'\n').decode()
    login_key = re.compile(".+KEY=(.+)\n").match(l_response).group(1)
    return login_key


def encrypt_password(password, hashkey):
    """Encrypt the password with the supplied hash from the server"""
    password = list(password)
    hashkey = list(hashkey[:32])
    return b''.join([struct.pack('B', ((char - 32) ^ hashkey[i]) + 32) for i, char in enumerate(password)])


def get_credentials():
    return {
        'username': input('Username: ').encode('ASCII'),
        'password': getpass.getpass().encode('ASCII'),
        'character': input('Character name: ').capitalize(),
    }


def eaccess_protocol(login_info):
    with Telnet(host=HOST, port=PORT) as client:
        login_info['hashkey'] = k_action(client)
        a_action(client, login_info)
        g_action(client)
        character_code = c_action(client, login_info['character'])
        l_response = l_action(client, character_code)
        print(l_response)


if __name__ == '__main__':
    creds = get_credentials()
    eaccess_protocol(creds)
