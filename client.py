import struct, re
from telnetlib import Telnet
import argparse

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

def a_action(username, password, key):
    """Inform the server of the user/pass"""
    encrypted_password = encrypt_password(password, key)
    return b'A\t' + username + b'\t' + encrypted_password + b'\n'

def k_action(client):
    """Sends request for key to encrypt password with"""
    client.write(b'K\n')
    return client.read_until(b'\n')

def g_action(client):
    """Tell the server what game you want"""
    client.write(b'G\t' + GAME_CODE + b'\n')
    return client.read_until(b'\n')

def c_action(client):
    """Poll server for list of characters, return server details"""
    client.write(b'C\n') # C Action
    c_response = client.read_until(b'\n')
    character_code = re.compile("C\t\d\t\d\t\d\t\d\t(.+)\t").match(c_response.decode()).group(1)
    return character_code

def l_action(client, character_code):
    """Inform server of which character to play, return the server response with connection info"""
    client.write(b'L\t' + character_code.encode('ASCII') + b'\t' + b'STORM\n')

def encrypt_password(password, hash):
    """Encrypt the password with the supplied hash from the server"""
    password = list(password)
    hashkey = list(hash[:HASH_LENGTH])
    return b''.join([struct.pack('B', ((char - 32) ^ hashkey[i]) + 32) for i, char in enumerate(password)])

HOST = 'eaccess.play.net'
PORT = 7900
HASH_LENGTH = 32
USERNAME = b'notausername'
PASSWORD = b'notapassword'
GAME_CODE = b'DR'

def eaccess_protocol():
    with Telnet(host=HOST, port=PORT) as client:
        key = k_action(client)
        assert len(key) == HASH_LENGTH + 1
        client.write(a_action(USERNAME, PASSWORD, key))
        a_response = client.read_until(b'\n')
        login_key = re.compile(".*\tKEY\t(.+)\t").match(a_response.decode()).group(1)
        g_response = g_action(client)
        character_code = c_action(client)
        l_response = l_action(client, character_code)
        client.interact()

