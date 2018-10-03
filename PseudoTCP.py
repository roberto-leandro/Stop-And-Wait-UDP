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

    @staticmethod
    def _are_flags_set(header, *flags):
        for flag in list(flags):
            if (flag & header) == 0:
                return False
        return True

    @staticmethod
    def _are_flags_unset(header, *flags):
        for flag in list(flags):
            if (flag & header) != 0:
                return False
        return True

    def bind(self, address):
        self.sock.bind(address)

    def accept(self):
        while True:
            try:
                received_message, address = self.sock.recvfrom(self.PACKET_SIZE)
            except socket.timeout:
                continue
            bits = [bin(x) for x in received_message]
            print(f"received {bits} from {address}")

            header = received_message[0]
            is_syn = self._are_flags_set(header, self.HEADER_SYN) and \
                self._are_flags_unset(header, self.HEADER_FIN | self.HEADER_ACK)
            if not is_syn:
                print("did not receive SYN, retrying")
                continue

            print("SYN received")
            message = bytearray(2)
            message[0] = self.HEADER_ACK | self.HEADER_SYN | self.HEADER_ACK_BIT
            print(f"HEADER {bin(message[0])}")
            bits = [bin(x) for x in message]
            print(f"sending {bits} to {address}")
            self.sock.sendto(message, address)

            try:
                new_received_message, address = self.sock.recvfrom(self.PACKET_SIZE)
            except socket.timeout:
                print("Timeout waiting for ACK")
                continue
            bits = [bin(x) for x in new_received_message]
            print(f"received new message {bits} from {address}")

            new_header = new_received_message[0]
            is_ack = self._are_flags_set(new_header, self.HEADER_ACK) and \
                self._are_flags_unset(new_header, self.HEADER_FIN, self.HEADER_SYN)
            if is_ack:
                print("ACK received")
                self.sock.connect(address)
                break
            print("Did not receive ACK, retrying")

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

    def send(self, message):
        frame_bit = True
        bytes_send = 0

        while bytes_send < len(message):
            # Make a packet and send to "connected" socket
            # TODO(Carlos): abstract the packet construction
            packet = bytearray(self.PACKET_SIZE)
            header = self.HEADER_FRAME_BIT if frame_bit else 0
            packet[0] = header
            packet[1] = message[bytes_send]
            self.sock.send(packet)

            try:
                maybe_ack_message = self.sock.recv(2)
            except socket.timeout:
                print("Timed out waiting for ACK")
                continue

            # Check if ack and ack bit is correct
            # TODO(Carlos): refactor into a macro
            # TODO(Carlos): check for other flags
            maybe_ack_header = maybe_ack_message[0]
            is_ack = self._are_flags_set(maybe_ack_header, self.HEADER_ACK)
            expected_ack_bit = self.HEADER_ACK_BIT if not frame_bit else 0
            is_ack_bit_correct = (maybe_ack_header | self.HEADER_ACK_BIT) == expected_ack_bit
            if not is_ack:
                # FIXME(Carlos): In a true full duplex this shouldn't happen
                print("Packet received is not ACK, resending packet")
                continue
            if not is_ack_bit_correct:
                # FIXME(Carlos): In this case we should wait for other packet or timeout, not resend instantly
                print("Packet received has incorrect ACK bit, possible duplicate")
                continue

            bytes_send += 1
            frame_bit = not frame_bit

    def recv(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError


node = PseudoTCPNode()
node.bind(("0.0.0.0", 65000))
node.accept()