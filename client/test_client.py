import selectors
import socket
import types

messages = [b'Message 1 from client.', b'Message 2 from client',]


def echo_client():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(('127.0.0.1', 10001))
        s.sendall(b'Hello, world')
        data = s.recv(1024)

    print('Received', repr(data))

def start_connections(sel, host, port, num_conns):
    server_addr = (host, port)
    for i in range(0, num_conns):
        connid = i + 1
        print('starting connection', connid, 'to', server_addr)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        sock.connect_ex(server_addr)
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        data = types.SimpleNamespace(connid=connid,
                                        msg_total=sum(len(m) for m in messages),
                                        recv_total=0,
                                        messages=list(messages),
                                        outb=b'')
        sel.register(sock, events, data=data)

def service_connection(sel, key, mask):
    sock = key.fileobj
    data = key.data
    if mask & selectors.EVENT_READ:
        recv_data = sock.recv(1024)  # Should be ready to read
        if recv_data:
            print("received", repr(recv_data), "from connection", data.connid)
            data.recv_total += len(recv_data)
            if not recv_data or data.recv_total == data.msg_total:
                print("closing connection", data.connid)
                sel.unregister(sock)
                sock.close()
    if mask & selectors.EVENT_WRITE:
        if not data.outb and data.messages:
            data.outb = data.messages.pop(0)
        if data.outb:
            print("sending", repr(data.outb), "to connection", data.connid)
            sent = sock.send(data.outb)  # Should be ready to write
            data.outb = data.outb[sent:]


def multi_connection_client():
    host = '127.0.0.1'
    port = 10001
    sel = selectors.DefaultSelector()
    
    try:
        start_connections(sel, host, port, 3)
        while True:
            events = sel.select()
            if events:
                for key, mask in events:
                    service_connection(sel, key, mask)
            if not sel.get_map():
                break
    except KeyboardInterrupt:
        print("Caught keyboard interrupt, exiting")
        sel.close()

if __name__ == '__main__':
    multi_connection_client()