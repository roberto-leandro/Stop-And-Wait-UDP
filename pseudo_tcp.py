import socket
import random
import queue
import threading
import states
import utility


class PseudoTCPSocket:

    # TODO add getters and setters for this class' variables to be used in the states module
    # TODO create a utility method to always send socket messages to the current partner
    # The getters and setters should encapsulate the acquiring and releasing of locks for queues, current_partner, etc
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.current_partner = None
        self.current_partner_lock = threading.Lock()
        self.current_status = states.ClosedStatus()
        self.current_sn = False
        self.current_rn = False
        self.send_queue = queue.Queue()
        self.receive_queue = queue.Queue()
        self.payload_queue = queue.Queue()

    def bind(self, address):
        self.sock.bind(address)
        self.start_permanent_loops()

    def accept(self):
        self.current_partner_lock.acquire()
        self.current_partner = None
        self.current_partner_lock.release()
        print("Waiting for incoming connections...")
        self.current_status = states.AcceptStatus

    def connect(self, address):
        # Change localhost to 127.0.0.1 from now so the address can be written as the current partner
        if address[0] == 'localhost':
            address = ('127.0.0.1', address[1])

        self.current_partner_lock.acquire()
        self.current_partner = address
        self.current_partner_lock.release()
        self.current_status = states.ClosedStatus
        self.sock.connect(address)
        print(f"Trying to connect to {address}...")

        # Build the SYN message, choosing a random value for sn
        self.current_sn = random.choice([True, False])
        syn_message = utility.create_packet(syn=True, sn=self.current_sn)
        # Send SYN
        print(f"Sending SYN {utility.packet_to_string(syn_message)} to {address}")
        self.sock.sendall(syn_message)
        self.current_status = states.SynSentStatus

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
                packet, address = self.sock.recvfrom(utility.PACKET_SIZE)
            except socket.timeout:
                continue

            print(f"Received a packet {utility.packet_to_string(packet)} from {address} with SN={utility.get_sn(packet[0])}"
                  f" and RN={utility.get_rn(packet[0])}.")
            if self.current_partner is None or address == self.current_partner:
                self.receive_queue.put((packet, address), block=True)

    def main_loop(self):
        """This loop will handle the three main events: receiving data from an upper layer, receiving an ack, or a
        timeout"""
        while True:
            try:
                # This call blocks until an element is available
                packet, address = self.receive_queue.get(block=True, timeout=utility.TIMEOUT)
            except queue.Empty:
                # Timed out waiting for a packet
                print(f"Timeout! Handling with current status {self.current_status.STATUS_NAME}")
                self.current_status.handle_timeout(self)

            print(f"Handling packet with current status {self.current_status.STATUS_NAME}")
            self.current_status.handle_packet(packet=packet, origin_address=address, node=self)

    def send(self, message):
        bytes_sent = 0

        while bytes_sent < len(message):
            # TODO add data left
            packet = utility.create_packet(sn=self.current_sn, rn=self.current_rn,
                                           payload=message[bytes_sent:bytes_sent + utility.PAYLOAD_SIZE])
            self.send_queue.put(packet, block=True)
            bytes_sent += utility.PAYLOAD_SIZE

    def recv(self, size):
        """Read from the processed message queue"""
        message = bytearray(size)
        received_bytes = 0
        self.current_sn = not self.current_sn
        while received_bytes < size:
            message[received_bytes:utility.PAYLOAD_SIZE:] = self.payload_queue.get(block=True)
            received_bytes += utility.PAYLOAD_SIZE
        return message

    def close(self):
        raise NotImplementedError
