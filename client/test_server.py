import socket
import selectors
import sys
import types

def echo_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 10001))
        s.listen()
        conn, addr = s.accept()
        with conn:
            print('Connected by', addr)
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                conn.sendall(data)

def multi_connection_server(**kwargs):
    def accept_wrapper(sock):
        conn, addr = sock.accept() # Should be ready to read
        print('accepted connection from ', addr)
        conn.setblocking(False)
        data = types.SimpleNamespace(addr=addr, inb=b'', outb=b'')
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        sel.register(conn, events, data=data)

    def service_connection(key, mask):
        sock = key.fileobj
        data = key.data
        if mask & selectors.EVENT_READ:
            recv_data = sock.recv(1024)
            if recv_data:
                data.outb += recv_data
            else:
                print('closing connection to ', data.addr)
                sel.unregister(sock)
                sock.close()
        if mask & selectors.EVENT_WRITE:
            if data.outb:
                print('echoing', repr(data.outb), 'to', data.addr)
                sent = sock.send(data.outb)
                data.outb = data.outb[sent:]

    # Set up listening socket
    host = '127.0.0.1'
    port = 10001
    sel = selectors.DefaultSelector()
    lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lsock.bind((host, port))
    lsock.listen()
    print('listening on ', (host, port))
    lsock.setblocking(False)
    # Register socket to be monitored
    sel.register(lsock, selectors.EVENT_READ, data=None)
    
    # Event Loop
    while True:
        # Block until sockets are ready for I/O
        events = sel.select(timeout=None)
        for key, mask in events:
            if key.data is None:
                accept_wrapper(key.fileobj)
            else:
                service_connection(key, mask)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("usage:", sys.argv[0], "<host> <port>")
        #sys.exit(1)

    if len(sys.argv) > 1:
        host, port = sys.argv[1], sys.argv[2]
    multi_connection_server()    