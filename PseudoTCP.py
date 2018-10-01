import socket
import struct

class PseudoTCPNode:
    HEADER_SIZE = 1
    PACKET_SIZE = 1
    SOCKET_TIMEOUT = .50
    HEADER_SYN = 0x01
    HEADER_ACK = 0x02
    HEADER_FIN = 0x04

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(PseudoTCPNode.SOCKET_TIMEOUT)

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
