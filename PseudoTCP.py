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

    @staticmethod
    def _are_flags_set(header, *flags):
        are_set = True
        for flag in list(flags):
            are_set = are_set && (flag & header != 0)
        return are_set

    def bind(self, address):
        self.sock.bind(address)

    def accept(self):
        while True:
            received_bytes = self.sock.recv(PseudoTCPNode.HEADER_SIZE)
            if not received_bytes:
                continue

            header = received_bytes[0]
            is_syn = self._are_flags_set(header, HEADER_SYN)
            if is_syn:
                break

        self.sock.send()

    def recv(self):
        pass

    def connect(self):
        pass

    def send(self):
        pass
