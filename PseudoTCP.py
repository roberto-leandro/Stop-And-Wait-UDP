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
            are_set = are_set and (flag & header != 0)
        return are_set

    def bind(self, address):
        self.sock.bind(address)

    def accept(self):
        while True:
            received_bytes = self.sock.recv(PseudoTCPNode.HEADER_SIZE)
            if not received_bytes:
                continue

            header = received_bytes[0]
            is_syn = self._are_flags_set(header, self.HEADER_SYN)
            if is_syn:
                break

        self.sock.send()

    def recv(self):
        pass

    def connect(self, address):
        print(f"Trying to connect to {address}...")

        # Instantiate a socket to send the data
        new_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        new_socket.settimeout(self.SOCKET_TIMEOUT)

        # Build the SYN message
        syn_message = bytearray(2)
        syn_message[0] = self.HEADER_SYN

        while True:
            # Send SYN
            print("Sending SYN...")
            new_socket.sendall(syn_message)

            # Wait for SYN-ACK
            syn_ack = new_socket.recv(PseudoTCPNode.HEADER_SIZE)

            # If a packet was received and it contains SYN-ACK, continue
            if syn_ack and self._are_flags_set(syn_ack, self.HEADER_SYN, self.HEADER_ACK):  # TODO check fin is unset
                print("Timeout! Trying again...")
                break

        # Send ACK
        new_socket.sendall(PseudoTCPNode.HEADER_ACK)

    def send(self):
        pass



