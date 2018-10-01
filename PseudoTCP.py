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
    HEADER_ACK_BIT = 0x010

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(PseudoTCPNode.SOCKET_TIMEOUT)

    @staticmethod
    def _are_flags_set(header, *flags):
        are_set = True
        for flag in list(flags):
            are_set = are_set and (flag & header != 0)
        return are_set

    @staticmethod
    def _are_flags_unset(header, *flags):
        are_unset = True
        for flag in list(flags):
            are_unset = are_unset and (flag & header == 0)
        return are_unset

    def bind(self, address):
        self.sock.bind(address)

    def recv(self):
        pass

    def connect(self, address):
        print(f"Trying to connect to {address}...")

        # Instantiate a socket to send the data
        new_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        new_socket.settimeout(self.SOCKET_TIMEOUT)
        new_socket.connect(address)

        # Build the SYN message
        syn_message = bytearray(2)
        syn_message[0] = self.HEADER_SYN | self.HEADER_FRAME_BIT

        while True:
            # Send SYN
            print("Sending SYN...")
            new_socket.sendall(syn_message)

            # Wait for SYN-ACK
            syn_ack = new_socket.recv(PseudoTCPNode.HEADER_SIZE)

            # If a packet was received and it contains SYN-ACK, continue
            if syn_ack and self._are_flags_set(syn_ack, self.HEADER_SYN, self.HEADER_ACK, self.HEADER_ACK_BIT)\
                    and self._are_flags_unset(syn_ack, self.HEADER_FIN, self.HEADER_FRAME_BIT):
                print("Timeout! (or the packet received was incorrect) Trying again...")
                break

        # Send ACK
        ack_message = bytearray(2)
        ack_message[0] = self.HEADER_ACK | self.HEADER_FRAME_BIT
        new_socket.sendall(PseudoTCPNode.HEADER_ACK)

    def send(self):
        pass
