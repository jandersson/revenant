from collections import deque
from datetime import datetime
import logging
import selectors
from types import SimpleNamespace
import sys

# from threading import Thread
from telnetlib import Telnet
from xml.etree.ElementTree import ParseError, XMLParser

# from client.login import simu_login
from client.client_logger import ClientLogger
from client.xml_data import XMLData


def is_windows():
    return sys.platform == "win32"


class Engine:
    """A basic DR client"""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.recv_buffer = deque(maxlen=1_000)
        self.send_buffer = deque(maxlen=100)
        self.log = ClientLogger().log
        self.sel = selectors.DefaultSelector()
        self.connection = Telnet()
        self.xml_data = XMLData()

    def connect(self):
        try:
            self.connection.open(self.host, self.port)
            sock = self.connection.get_socket()
            sock.setblocking(False)
            events = selectors.EVENT_READ | selectors.EVENT_WRITE
            data = SimpleNamespace(
                recv_total=0, sent_total=0, outb="", inb="", last_recv=None
            )
            self.sel.register(sock, events, data=data)
            # connection = simu_login()
        except Exception as error:
            self.log.error("Failed to connect")
            self.log.error(error)
            self.connection.close()
            sys.exit(1)

    def disconnect(self):
        self.log.info("Disconnecting")
        # self.sel.unregister(self.connection.get_socket())
        # self.sel.close()
        self.connection.close()
        sys.exit()

    def run_reactor(self, key, mask):
        sock = key.fileobj
        data = key.data
        if mask & selectors.EVENT_READ:
            recv_data = sock.recv(4096)
            if recv_data:
                data.recv_total += len(recv_data)
                data.last_recv = datetime.now()
                self.recv_buffer.append(recv_data)
                print(recv_data)
            if not recv_data:
                self.disconnect()
        if mask & selectors.EVENT_WRITE:
            if data.outb:
                self.send_buffer.append(data.outb)
                sent = sock.send(data.outb)
                data.outb = data.outb[sent:]

    def reactor(self):
        """A very basic implementation of handling input/output"""
        try:
            while True:
                self.service_client()
                events = self.sel.select(timeout=1)
                if events:
                    for key, mask in events:
                        self.service_connection(key, mask)
                if not self.sel.get_map():
                    break
        except KeyboardInterrupt:
            print("Caught keyboard interrupt")
        finally:
            self.disconnect()

    def write(self):
        write_data = input()
        print(f"> {write_data}")
        self.connection.write((write_data + "\n").encode("ASCII"))

    def read(self, output_callback=None):
        buff = []

        try:
            read_data = self.connection.read_very_eager().decode("ASCII")
        except EOFError as e:
            goodbye = """
            ******************
            *****THE END******
            ******************

            """.split(
                "\n"
            )
            if output_callback:
                output_callback(goodbye)
            else:
                buff.append(goodbye)
            self.log.info("Connection closed")
            raise (e)

        for line in read_data.split("\n"):

            # TODO: This if might be redundant
            if line:
                logging.getLogger("game").info(line)
                try:
                    XMLParser(target=self.xml_data).feed(line)
                except ParseError:
                    pass
                line = self.xml_data.strip(line)
                if not line:
                    continue
                if output_callback:
                    output_callback(line)
                else:
                    buff.append(line)

        if not output_callback:
            sys.stdout.write("\n".join(buff))
            sys.stdout.flush()


if __name__ == "__main__":
    engine = Engine("aardwolf.org", 4000)
    engine.connect()
    engine.reactor()
