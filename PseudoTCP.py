import socket
import struct

class PseudoTCPNode:
    HEADER_SIZE = 1
    PAYLOAD_SIZE = 1
    PACKET_SIZE = HEADER_SIZE + PAYLOAD_SIZE
    SOCKET_TIMEOUT = .50
    HEADER_SYN = 0x01
    HEADER_ACK = 0x02
    HEADER_FIN = 0x04
    HEADER_FRAME_BIT = 0x08
    HEADER_ACK_BIT = 0x0F

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(PseudoTCPNode.SOCKET_TIMEOUT)

    @staticmethod
    def _are_flags_set(header, *flags):
        are_set = True
        for flag in list(flags):
            are_set = are_set && (flag & header != 0)
        return are_set

    @staticmethod
    def _are_flags_unset(header, *flags):
        are_unset = True
        for flag in list(flags):
            are_unset = are_set and (flag & header == 0)
        return are_set

    def bind(self, address):
        self.sock.bind(address)

    def accept(self):
        while True:
            received_message = None
            while received_message == None:
                received_message = self.sock.recv(PseudoTCPNode.PACKET_SIZE)

            header = received_message[0]
            frame_bit = header | HEADER_FRAME_BIT
            is_syn = self._are_flags_set(header, HEADER_SYN) and \
                     self._are_flags_unset(header, HEADER_FIN | HEADER_ACK)
            if not is_syn:
                continue

            message = bytearray(2)
            message[0] = message[0] | HEADER_ACK | HEADER_SYN | frame_bit
            self.sock.send(message)

            new_received_message = None
            while new_received_message == None:
                new_received_message = self.sock.recv(PseudoTCPNode.PACKET_SIZE)

            new_header = new_received_message[0]
            is_ack = self._are_flags_set(header, HEADER_ACK) and \
                     self._are_flags_unset(header, HEADER_FIN, HEADER_SYN)
            break
            

    def recv(self):
        pass

    def connect(self):
        pass

    def send(self):
        pass
