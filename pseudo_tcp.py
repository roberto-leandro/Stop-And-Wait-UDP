import socket
import random
import queue
import threading
import states
import utility


class PseudoTCPSocket:

    # TODO handshake does not happen properly, sometimes the node thinks it's receiving data when receiving an ACK, or
    # viceversa
    # TODO the message does not start being sent when send() is called, instead it starts after a timeout
    # TODO log all the prints to a file
    # TODO close mechanism
    # TODO add data_left to the header of each packet in send()
    # TODO add a random chance to "lose" packets
    def __init__(self):
        # Socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # State variables
        self.current_status = states.ClosedStatus()
        self.current_sn = False
        self.current_rn = False
        self.current_partner = None
        
        # Queues 
        self.send_queue = queue.Queue()
        self.receive_queue = queue.Queue()
        self.payload_queue = queue.Queue()
        
        # Locks
        self.sock_read_lock = threading.Lock()
        self.sock_write_lock = threading.Lock()
        self.current_partner_lock = threading.Lock()
        self.current_status_lock = threading.Lock()
        self.current_sn_lock = threading.Lock()
        self.current_rn_lock = threading.Lock()
        self.send_queue_lock = threading.Lock()  # Necessary for the implementation of peek_send_queue()

    def bind(self, address):
        self.sock.bind(address)
        self.start_permanent_loops()

    def accept(self):
        print("Waiting for incoming connections...")
        self.set_current_partner(None)
        self.set_current_status(states.AcceptStatus())

    def connect(self, address):
        # Change localhost to 127.0.0.1 from now so the address can be written as the current partner
        if address[0] == 'localhost':
            address = ('127.0.0.1', address[1])

        self.set_current_partner(address)
        self.set_current_status(states.ClosedStatus())
        self.sock.connect(address)
        print(f"Trying to connect to {address}...")

        # Build the SYN message, choosing a random value for sn
        self.set_current_sn(random.randint(0, 255))
        syn_message = utility.create_packet(syn=True, sn=self.get_current_sn())
        # Send SYN
        print(f"Sending SYN...")
        self.send_packet(syn_message)
        self.set_current_status(states.SynSentStatus())

    def start_permanent_loops(self):
        main_looper = threading.Thread(target=self.main_loop)
        reader = threading.Thread(target=self.read_loop)
        main_looper.start()
        reader.start()
        print("Loops started!")

    def read_loop(self):
        """Puts packets in the receive queue"""
        while True:
            packet, address = self.receive_packet()

            if self.current_partner is None or address == self.current_partner:
                # Add the packet to the receive queue only if it was received from the current partner
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
                print(f"Timeout! Handling with current status {self.get_current_status().STATUS_NAME}")
                self.get_current_status().handle_timeout(self)
                continue

            print(f"Handling packet with current status {self.get_current_status().STATUS_NAME}")
            self.get_current_status().handle_packet(packet=packet, origin_address=address, node=self)

    def send(self, message):
        bytes_sent = 0

        while bytes_sent < len(message):
            # TODO add data left
            packet = utility.create_packet(payload=message[bytes_sent:bytes_sent + utility.PAYLOAD_SIZE])
            self.send_queue.put(packet, block=True)
            bytes_sent += utility.PAYLOAD_SIZE

    # TODO modify implementation to read the data remaining from the packet's headers
    # TODO add a random chance to "lose" packets
    def recv(self, size):
        """Read from the processed message queue until data_left is 0"""
        message = bytearray(size)
        received_bytes = 0
        self.current_sn = not self.current_sn
        while received_bytes < size:
            message[received_bytes:utility.PAYLOAD_SIZE:] = self.payload_queue.get(block=True)
            received_bytes += utility.PAYLOAD_SIZE
        return message

    def close(self):
        raise NotImplementedError

    def peek_send_queue(self):
        self.send_queue_lock.acquire()
        first_packet = self.send_queue.queue[0]
        self.send_queue_lock.release()
        return first_packet

    def send_packet(self, packet):
        # Write RN and SN
        packet[1] = self.get_current_rn()
        packet[2] = self.get_current_sn()

        print(f"Sending packet {utility.packet_to_string(packet)} with SN={utility.get_sn(packet)} and "
              f"RN={utility.get_rn(packet)} and ACK={utility.are_flags_set(packet, utility.HEADER_ACK)} to "
              f"{self.get_current_partner()}")

        self.sock_write_lock.acquire()
        self.sock.sendto(packet, self.get_current_partner())
        self.sock_write_lock.release()

    def receive_packet(self):
        self.sock_read_lock.acquire()
        packet, address = self.sock.recvfrom(utility.PACKET_SIZE)
        self.sock_read_lock.release()
        print(f"Received packet {utility.packet_to_string(packet)} with SN={utility.get_sn(packet)} and "
              f"RN={utility.get_rn(packet)} and ACK={utility.are_flags_set(packet, utility.HEADER_ACK)} "
              f"from {address}")
        return packet, address

    def get_current_sn(self):
        sn = None
        self.current_sn_lock.acquire()
        sn = self.current_sn
        self.current_sn_lock.release()
        return sn
    
    def set_current_sn(self, sn):
        self.current_sn_lock.acquire()
        self.current_sn = sn
        self.current_sn_lock.release()

    def increase_current_sn(self):
        self.current_sn_lock.acquire()
        # TODO parametrisize rn max size
        self.current_sn = 1 + self.current_sn % 255
        self.current_sn_lock.release()

    def get_current_rn(self):
        rn = None
        self.current_rn_lock.acquire()
        rn = self.current_rn
        self.current_rn_lock.release()
        return rn
    
    def set_current_rn(self, rn):
        self.current_rn_lock.acquire()
        self.current_rn = rn
        self.current_rn_lock.release()

    def increase_current_rn(self):
        self.current_rn_lock.acquire()
        self.current_rn = 1 + self.current_rn % 255
        self.current_rn_lock.release()

    def get_current_partner(self):
        partner = None
        self.current_partner_lock.acquire()
        partner = self.current_partner
        self.current_partner_lock.release()
        return partner

    def set_current_partner(self, new_partner):
        self.current_partner_lock.acquire()
        self.current_partner = new_partner

        # Partner has changed, the received queue should be emptied
        # TODO lock for the queue
        self.receive_queue = queue.Queue()

        self.current_partner_lock.release()

    def get_current_status(self):
        status = None
        self.current_status_lock.acquire()
        status = self.current_status
        self.current_status_lock.release()
        return status

    def set_current_status(self, new_status):
        self.current_status_lock.acquire()
        self.current_status = new_status
        self.current_status_lock.release()
