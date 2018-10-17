import socket
import random
import struct


class PseudoTCPSocket:
    HEADER_SIZE = 1
    PAYLOAD_SIZE = 2
    PACKET_SIZE = HEADER_SIZE + PAYLOAD_SIZE
    SOCKET_TIMEOUT = 3
    HEADER_SYN =       0b0000000010000000
    HEADER_ACK =       0b0000000001000000
    HEADER_FIN =       0b0000000000100000
    HEADER_SN =        0b0000000000010000
    HEADER_RN =        0b0000000000001000
    HEADER_DATA_LEFT = 0b0000000000000111

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(PseudoTCPSocket.SOCKET_TIMEOUT)
        self.current_partner = None
        self.current_status = 'CLOSED'
        self.current_sn = False
        self.current_rn = False


    @staticmethod
    def _packet_to_string(packet):
        return bin(int.from_bytes(packet, byteorder='big', signed=False))

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

    @staticmethod
    def _get_sn(header):
        if (PseudoTCPSocket.HEADER_SN & header) == 0:
            return False
        return True

    @staticmethod
    def _get_rn(header):
        if (PseudoTCPSocket.HEADER_RN & header) == 0:
            return False
        return True

    def _create_packet(self, syn=False, ack=False, fin=False, sn=False, rn=False, data_left=0, payload=bytearray(1)):
        packet = bytearray(2)

        # Set flags
        if syn:
            packet[0] = packet[0] | self.HEADER_SYN
        if ack:
            packet[0] = packet[0] | self.HEADER_ACK
        if fin:
            packet[0] = packet[0] | self.HEADER_FIN
        if sn:
            packet[0] = packet[0] | self.HEADER_SN
        if rn:
            packet[0] = packet[0] | self.HEADER_RN

        # Add data left and payload
        packet[0] = packet[0] | data_left
        packet[1] = int.from_bytes(payload, byteorder='big', signed=False)
        return packet

    def bind(self, address):
        self.sock.bind(address)

    def accept(self):
        print("Waiting for incoming connections...")
        self.current_status = 'LISTEN'
        is_syn = False
        while not is_syn:
            try:
                received_message, address = self.sock.recvfrom(self.PACKET_SIZE)
            except socket.timeout:
                continue

            print(f"Received {self._packet_to_string(received_message)} from {address}")

            # Check if message contains a valid SYN
            header = received_message[0]
            is_syn = self._are_flags_set(header, self.HEADER_SYN) and \
                self._are_flags_unset(header, self.HEADER_FIN | self.HEADER_ACK)

            if not is_syn:
                print("Message received was not a proper SYN, retrying...")

        print("The packet received was a valid SYN!")

        # Set the state variables to synchronize with the partner
        self.current_status = 'SYN RECEIVED'
        self.current_partner = address
        self.current_rn = not self._get_sn(header)
        self.current_sn = random.choice([True, False])

        # Send SYN-ACK
        syn_ack_message = self._create_packet(syn=True, ack=True, sn=self.current_sn, rn=self.current_rn)
        print(f"Sending {self._packet_to_string(syn_ack_message)} to {address}")
        self.sock.sendto(syn_ack_message, address)

        # Wait for ACK
        print(f"Waiting for ACK from {address}")
        is_ack = False
        while not is_ack:
            try:
                new_received_message, address = self.sock.recvfrom(self.PACKET_SIZE)
            except socket.timeout:
                continue

            print(f"Received {self._packet_to_string(new_received_message)} from {address}")

            # Check if the message was received from the address with which the connection is being established
            if not address == self.current_partner:
                print(f"{address} is not the address currently in the handshake process, ignoring and waiting for "
                      f"message from {self.current_partner}...")
                continue

            # Check if the packet contains ACK and has a correct rn (different from current sn)
            new_header = new_received_message[0]
            is_ack = self._are_flags_set(new_header, self.HEADER_ACK) \
                     and self._get_rn(new_header) != self.current_sn \
                     and self._are_flags_unset(new_header, self.HEADER_FIN, self.HEADER_SYN)

            if not is_ack:
                print("Message received was not a proper ACK, retrying...")

        print("Message received was a proper ACK!")
        # Update current variables: connection is now established, sn and rn should be flipped
        self.current_status = "ESTABLISHED"
        self.current_sn = not self.current_sn
        self.current_rn = not self._get_sn(new_header)

        self.sock.connect(address)

    def connect(self, address):
        self.current_status = "CLOSED"
        self.current_partner = address
        print(f"Trying to connect to {address}...")

        # Instantiate a socket to send the data
        new_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        new_socket.settimeout(self.SOCKET_TIMEOUT)
        new_socket.connect(address)

        # Build the SYN message, choosing a random value for sn
        self.current_sn = random.choice([True, False])
        syn_message = self._create_packet(syn=True, sn=self.current_sn)

        while True:
            # Send SYN
            print(f"Sending SYN {self._packet_to_string(syn_message)} to {address}")
            new_socket.sendall(syn_message)
            self.current_status = "SYN SENT"

            # Wait for SYN-ACK
            try:
                received_message, incoming_address = new_socket.recvfrom(PseudoTCPSocket.PACKET_SIZE)
            except socket.timeout:
                print("Timeout! Trying again...")
                continue

            syn_ack_header = received_message[0]
            print(f"Received {self._packet_to_string(received_message)} from {incoming_address}!")

            if not incoming_address == self.current_partner:
                print(f"{incoming_address} is not the address currently in the handshake process, ignoring and waiting "
                      f"for message from {self.current_partner}...")
                continue

            # Check if the packet contains SYN-ACK and has a correct rn (different from current sn)
            if syn_ack_header and self._are_flags_set(syn_ack_header, self.HEADER_SYN, self.HEADER_ACK)\
                    and self._get_rn(syn_ack_header) != self.current_sn \
                    and self._are_flags_unset(syn_ack_header, self.HEADER_FIN):
                break

            # Otherwise try again
            print("The packet received was not a valid SYN-ACK! Trying again...")

        print("The packet received contained a correct SYN-ACK!")
        # Update current variables: connection is now established, sn and rn should be flipped
        self.current_status = "ESTABLISHED"
        self.current_sn = not self.current_sn
        self.current_rn = not self._get_sn(syn_ack_header)

        # Send ACK
        ack_message = self._create_packet(ack=True, sn=self.current_sn, rn=self.current_rn)
        print(f"Sending ACK {self._packet_to_string(ack_message)}")
        new_socket.sendall(ack_message)

    def send(self, message):
        frame_bit = True
        bytes_send = 0

        while bytes_send < len(message):
            # Make a packet and send to "connected" socket
            # TODO(Carlos): abstract the packet construction
            packet = bytearray(self.PACKET_SIZE)
            header = self.HEADER_SN if frame_bit else 0
            packet[0] = header
            packet[self.HEADER_SIZE:] = message[bytes_send:self.PAYLOAD_SIZE:]
            self.sock.send(packet)

            try:
                maybe_ack_message = self.sock.recv(self.PACKET_SIZE)
            except socket.timeout:
                print("Timed out waiting for ACK, sending packet again.")
                continue

            # Check if ack and ack bit is correct
            # TODO(Carlos): refactor into a macro
            # TODO(Carlos): check for other flags
            maybe_ack_header = maybe_ack_message[0]
            is_ack = self._are_flags_set(maybe_ack_header, self.HEADER_ACK)
            expected_ack_bit = self.HEADER_RN if not frame_bit else 0
            is_ack_bit_correct = (maybe_ack_header | self.HEADER_RN) == expected_ack_bit
            if not is_ack:
                # FIXME(Carlos): In a true full duplex this shouldn't happen
                print("Packet received is not ACK, resending packet.")
                continue
            if not is_ack_bit_correct:
                # FIXME(Carlos): In this case we should wait for other packet or timeout, not resend instantly
                print("Packet received has incorrect ACK bit, possible duplicate.")
                continue

            bytes_send += self.PAYLOAD_SIZE
            frame_bit = not frame_bit

    def recv(self, size):
        message = bytearray(size)
        received_bytes = 0
        last_frame_bit = None
        while received_bytes < size:
            # Receive packet
            try:
                rec_packet = self.sock.recv(self.PACKET_SIZE)
            except socket.timeout:
                print("Timed out waiting for packet")
                continue
            header = rec_packet[0]
            rec_frame_bit = (header | self.HEADER_SN) != 0

            # Check if packet is duplicate
            if last_frame_bit is not None:
                last_frame_bit = rec_frame_bit
            elif last_frame_bit == rec_frame_bit:
                # ACK and ignore dup packet
                dup_ack = bytearray(2)
                frame_bit = 0 if last_frame_bit else self.HEADER_SN
                dup_ack[0] = self.HEADER_ACK | frame_bit
                self.sock.send(dup_ack)
                continue

            # Save the payload into the message
            message[received_bytes:self.PAYLOAD_SIZE:] = rec_packet[self.HEADER_SIZE:]

            # ACK the sender
            ack_message = bytearray(2)
            frame_bit = 0 if last_frame_bit else self.HEADER_SN
            ack_message[0] = self.HEADER_ACK | frame_bit
            self.sock.send(ack_message)
            received_bytes += self.PAYLOAD_SIZE

    def close(self):
        raise NotImplementedError
