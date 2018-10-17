import socket
import random
import queue
import threading


class PseudoTCPSocket:
    HEADER_SIZE = 1
    PAYLOAD_SIZE = 1
    PACKET_SIZE = HEADER_SIZE + PAYLOAD_SIZE
    SOCKET_TIMEOUT = 3
    HEADER_SYN = 0b0000000010000000
    HEADER_ACK = 0b0000000001000000
    HEADER_FIN = 0b0000000000100000
    HEADER_SN = 0b0000000000010000
    HEADER_RN = 0b0000000000001000
    HEADER_MESSAGE_END = 0b0000000000000100

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.current_partner = None
        self.current_partner_lock = threading.Lock()
        self.current_status = 'CLOSED'
        self.current_sn = False
        self.current_rn = False
        self.send_queue = queue.Queue()
        self.receive_queue = queue.Queue()
        self.payload_queue = queue.Queue()

    @staticmethod
    def _packet_to_string(packet):
        return bin(int.from_bytes(packet, byteorder='little', signed=False))

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

    @staticmethod
    def _create_packet(syn=False, ack=False, fin=False, sn=False, rn=False, data_left=0, payload=bytearray(1)):
        packet = bytearray(PseudoTCPSocket.PACKET_SIZE)

        # Set flags
        if syn:
            packet[0] = packet[0] | PseudoTCPSocket.HEADER_SYN
        if ack:
            packet[0] = packet[0] | PseudoTCPSocket.HEADER_ACK
        if fin:
            packet[0] = packet[0] | PseudoTCPSocket.HEADER_FIN
        if sn:
            packet[0] = packet[0] | PseudoTCPSocket.HEADER_SN
        if rn:
            packet[0] = packet[0] | PseudoTCPSocket.HEADER_RN

        # Add data left and payload
        packet[0] = packet[0] | data_left
        packet[PseudoTCPSocket.PAYLOAD_SIZE:] = payload
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
        self.current_partner_lock.acquire()
        self.current_partner = address
        self.current_partner_lock.release()
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
                     and self._get_sn(new_header) == self.current_rn \
                     and self._get_rn(new_header) != self.current_sn \
                     and self._are_flags_unset(new_header, self.HEADER_FIN, self.HEADER_SYN)

            if not is_ack:
                print("Message received was not a proper ACK, retrying...")

        print("Message received was a proper ACK!")
        # Update current variables: connection is now established, sn and rn should be flipped
        self.current_status = "ESTABLISHED"
        self.current_sn = self._get_rn(new_header)
        self.current_rn = not self._get_sn(new_header)
        self.start_permanent_loops()

    def connect(self, address):
        # Change localhost to 127.0.0.1 from now so the address can be written as the current partner
        if address[0] == 'localhost':
            address = ('127.0.0.1', address[1])

        self.current_partner_lock.acquire()
        self.current_partner = address
        self.current_partner_lock.release()
        self.current_status = "CLOSED"
        self.sock.connect(address)
        print(f"Trying to connect to {address}...")

        # Build the SYN message, choosing a random value for sn
        self.current_sn = random.choice([True, False])
        syn_message = self._create_packet(syn=True, sn=self.current_sn)

        while True:
            # Send SYN
            print(f"Sending SYN {self._packet_to_string(syn_message)} to {address}")
            self.sock.sendall(syn_message)
            self.current_status = "SYN SENT"

            # Wait for SYN-ACK
            try:
                received_message, incoming_address = self.sock.recvfrom(PseudoTCPSocket.PACKET_SIZE)
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
            if syn_ack_header and self._are_flags_set(syn_ack_header, self.HEADER_SYN, self.HEADER_ACK) \
                    and self._get_rn(syn_ack_header) != self.current_sn \
                    and self._are_flags_unset(syn_ack_header, self.HEADER_FIN):
                break

            # Otherwise try again
            print("The packet received was not a valid SYN-ACK! Trying again...")

        print("The packet received contained a correct SYN-ACK!")
        # Update current variables: connection is now established, sn and rn should be flipped
        self.current_status = "ESTABLISHED"
        self.current_sn = self._get_rn(syn_ack_header)
        self.current_rn = not self._get_sn(syn_ack_header)

        # Send ACK
        ack_message = self._create_packet(ack=True, sn=self.current_sn, rn=self.current_rn)
        print(f"Sending ACK {self._packet_to_string(ack_message)}")
        self.sock.sendall(ack_message)
        self.start_permanent_loops()

    def start_permanent_loops(self):
        main_looper = threading.Thread(target=self.main_loop)
        reader = threading.Thread(target=self.read_loop)
        main_looper.start()
        reader.start()
        print("Loops started!")

    def read_loop(self):
        """Puts packets in the receive queue"""
        while True:
            try:
                packet, address = self.sock.recvfrom(self.PACKET_SIZE)
            except socket.timeout:
                continue
            if address == self.current_partner:
                self.receive_queue.put(packet, block=True)


    def main_loop(self):
        """This loop will handle the three main events: receiving data from an upper layer, receiving an ack, or a timeout"""
        while True:
            if not self.receive_queue.empty():
                is_valid = False
                packet = self.receive_queue.get(block=True)

                # Process the packet, determine if its valid and if an ACK should be sent
                print(f"Got new packet {self._packet_to_string(packet)}")
                header = packet[0]

                # Check if packet contains new data
                if self._get_sn(header) == self.current_rn:
                    is_valid = True
                    print("Packet contains new data!")

                    # Put the payload in the proccessed messages queue
                    self.payload_queue.put(packet[self.HEADER_SIZE:])

                    # Increase rn
                    self.current_rn = not self.current_rn

                    # ACK the sender
                    ack_message = self._create_packet(ack=True, sn=self.current_sn, rn=self.current_rn)
                    print(f"Sending ACK {self._packet_to_string(ack_message)}")
                    self.sock.sendto(ack_message, self.current_partner)

                # Check if packet contains an ACK
                if self._are_flags_set(header, self.HEADER_ACK) and self._get_rn(header) != self.current_sn:
                    is_valid = True
                    print("Packet contains an ACK!")
                    self.current_sn = self._get_rn(header)

                    # Send next packet
                    self.sock.sendto(self.send_queue.get(block=True), self.current_partner)

                if not is_valid:
                    print("Packet did not contain anything useful...")

    def send(self, message):
        bytes_sent = 0

        while bytes_sent < len(message):
            packet = self._create_packet(sn=self.current_sn, rn=self.current_rn,
                                         payload=message[bytes_sent:bytes_sent + self.PAYLOAD_SIZE])
            self.send_queue.put(packet, block=True)
            bytes_sent += self.PAYLOAD_SIZE
        self.sock.sendto(self.send_queue.get(block=True), self.current_partner)

    def recv(self, size):
        """Read from the processed message queue"""
        message = bytearray(size)
        received_bytes = 0
        self.current_sn = not self.current_sn
        while received_bytes < size:
            message[received_bytes:self.PAYLOAD_SIZE:] = self.payload_queue.get(block=True)
            received_bytes += self.PAYLOAD_SIZE
        return message

    def close(self):
        raise NotImplementedError
