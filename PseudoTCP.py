import socket

class PseudoTCPNode:
    PACKET_SIZE = 1
    SOCKET_TIMEOUT = 50

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def bind(self, address):
        self.sock.bind(address)

    def accept(self):
        pass

    def recv(self):
        pass

    def connect(self):
        pass

    def send(self):
        pass
