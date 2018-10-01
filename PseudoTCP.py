import socket
import struct

class PseudoTCPNode:
    HEADER_SIZE = 1
    PAYLOAD_SIZE = 1
    PACKET_SIZE = HEADER_SIZE + PAYLOAD_SIZE
    SOCKET_TIMEOUT = 3
    HEADER_SYN = 0x01
    HEADER_ACK = 0x02
    HEADER_FIN = 0x04
    HEADER_FRAME_BIT = 0x08
    HEADER_ACK_BIT = 0x10

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(PseudoTCPNode.SOCKET_TIMEOUT)
        self.connection = None

    @staticmethod
    def _are_flags_set(header, *flags):
        are_set = True
        for flag in list(flags):
            are_set = are_set and (flag & header) != 0
        return are_set

    @staticmethod
    def _are_flags_unset(header, *flags):
        are_unset = True
        for flag in list(flags):
            are_unset = are_unset and int((int(flag) & int(header)) == 0)
        return are_unset

    def bind(self, address):
        self.sock.bind(address)

    def accept(self):
        while True:
            received_message = None
            while received_message == None:
                received_message, address = self.sock.recvfrom(self.PACKET_SIZE)

            header = received_message[0]
            frame_bit = header | self.HEADER_FRAME_BIT
            is_syn = self._are_flags_set(header, self.HEADER_SYN) and \
                     self._are_flags_unset(header, self.HEADER_FIN | self.HEADER_ACK)
            if not is_syn:
                continue

            message = bytearray(2)
            message[0] = message[0] | self.HEADER_ACK | self.HEADER_SYN | frame_bit
            self.sock.send(message)

            new_received_message = None
            while new_received_message == None:
                new_received_message, address = self.sock.recv(self.PACKET_SIZE)

            new_header = new_received_message[0]
            is_ack = self._are_flags_set(header, self.HEADER_ACK) and \
                     self._are_flags_unset(header, self.HEADER_FIN, self.HEADER_SYN)
            self.connection = address
            break

    def connect(self):
        pass

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
            print(f"Sending SYN {syn_message} to {address}")
            new_socket.sendall(syn_message)

            # Wait for SYN-ACK
            try:
                received_message, incoming_address = new_socket.recvfrom(PseudoTCPNode.PACKET_SIZE)
            except socket.timeout:
                print("Timeout! Trying again...")
                continue

            syn_ack_header = received_message[0]
            print(f"Received {bin(syn_ack_header)} from {incoming_address}!")

            # If a packet was received and it contains SYN-ACK, continue
            if syn_ack_header and self._are_flags_set(syn_ack_header, self.HEADER_SYN, self.HEADER_ACK, self.HEADER_ACK_BIT)\
                    and self._are_flags_unset(syn_ack_header, self.HEADER_FIN, self.HEADER_FRAME_BIT):
                break

            # Otherwise try again
            print("The packet received was incorrect! Trying again...")

        # Send ACK
        ack_message = bytearray(2)
        ack_message[0] = self.HEADER_ACK | self.HEADER_FRAME_BIT
        print(f"Sending {ack_message}")
        new_socket.sendall(ack_message)

    def send(self):
        pass
