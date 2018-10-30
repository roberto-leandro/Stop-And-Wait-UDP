import random
import queue
import threading
import states
import utility


class PseudoTCPSocket:

    # TODO the message does not start being sent when send() is called, instead it starts after a timeout
    # TODO log all the prints to a file
    # TODO close mechanism
    # TODO pick a good timeout
    def __init__(self, address, sock, sock_lock, finished_message_queue):
        # Change localhost to 127.0.0.1 from now so the address can be written as the current partner
        if address[0] == 'localhost':
            address = ('127.0.0.1', address[1])

        # Socket
        self.sock = sock
        
        # State variables
        self.current_status = states.ClosedStatus()
        self.current_sn = 0
        self.current_rn = 0
        self.partner = address

        self.stopper = threading.Event()

        # Queues
        self.send_queue = queue.Queue()
        self.receive_queue = queue.Queue()
        self.payload_queue = queue.Queue()
        self.finished_message_queue = finished_message_queue

        # Locks
        self.sock_read_lock = threading.Lock()
        self.sock_send_lock = sock_lock
        self.send_queue_lock = threading.Lock()
        self.current_status_lock = threading.Lock()
        self.current_sn_lock = threading.Lock()
        self.current_rn_lock = threading.Lock()

        # Threads
        self.main_thread = threading.Thread(target=self.main_loop)
        self.main_thread.start()
        self.message_assembler = threading.Thread(target=self.assemble_message_loop)
        self.message_assembler.start()

    def initiate_connection(self):
        print(f"Trying to connect to {self.partner}...")

        # Build the SYN message, choosing a random value for sn
        self.set_current_sn(random.randint(0, 255))
        syn_message = utility.create_packet(syn=True, sn=self.get_current_sn())
        # Send SYN
        print(f"Sending SYN...")
        self.send_packet(syn_message)
        self.set_current_status(states.SynSentStatus())

        # Send SYN is the send_queue, as it might need to be resent if the packet is lost
        self.send_queue.put(syn_message)

    def main_loop(self):
        """This loop will handle the three main events: receiving data from an upper layer, receiving an ack, or a
        timeout"""
        while not self.stopper.is_set():
            try:
                # This call blocks until an element is available
                packet = self.receive_queue.get(block=True, timeout=utility.TIMEOUT)
            except queue.Empty:
                # Timed out waiting for a packet
                print(f"Timeout! Handling with current status {self.get_current_status().STATUS_NAME}")
                self.get_current_status().handle_timeout(self)
                continue

            print(f"Handling packet with current status {self.get_current_status().STATUS_NAME}")
            self.get_current_status().handle_packet(packet=packet, node=self)
        print("Stopped main loop")

    def assemble_message_loop(self):
        """Assemble the payload fragments into a message, and send it to upper layer"""
        message = bytearray()
        received_bytes = 0
        # Read until end of transmission
        while not self.stopper.is_set():
            current_payload = self.payload_queue.get(block=True)

            if current_payload == 0x4:
                # Message ended, put it in the finished_message_queue and reset variables
                print("Finished reading a message!")
                self.finished_message_queue.put(message, self.partner)
                message = bytearray()
                received_bytes = 0

            else:
                # Add the next payload to the message
                message[received_bytes:utility.PAYLOAD_SIZE:] = current_payload
                received_bytes += utility.PAYLOAD_SIZE

    def send(self, message):
        bytes_sent = 0
        self.send_queue_lock.acquire()
        while bytes_sent < len(message):
            if bytes_sent + utility.PAYLOAD_SIZE > len(message):
                # For the last packet, data left is the amount of bytes to be read in the payload
                data_left = len(message) - bytes_sent
            else:
                # For all packets except the last one, all data left bits are turned on
                data_left = utility.HEADER_DATA_LEFT

            packet = utility.create_packet(data_left=data_left,
                                           payload=message[bytes_sent:bytes_sent + utility.PAYLOAD_SIZE])
            self.send_queue.put(packet)
            bytes_sent += utility.PAYLOAD_SIZE
        self.send_queue_lock.release()

    def close(self):
        # Block until all task in the queue are done
        self.send_queue.join()
        close_packet = utility.create_packet(fin=True, sn=self.get_current_sn(), rn=self.get_current_rn())
        self.increase_current_sn()
        self.send_packet(close_packet)
        self.send_queue.put(close_packet)
        self.set_current_status(states.CloseSentStatus)

    def peek_send_queue(self):
        with self.send_queue.mutex:
            first_packet = self.send_queue.queue[0]
        return first_packet

    def send_packet(self, packet):
        # Write RN and SN
        packet[1] = self.get_current_rn()
        packet[2] = self.get_current_sn()

        print(f"Sending packet {utility.packet_to_string(packet)} with SN={utility.get_sn(packet)} and "
              f"RN={utility.get_rn(packet)} and ACK={utility.are_flags_set(packet, utility.HEADER_ACK)} to "
              f"{self.get_partner()}")

        self.sock_send_lock.acquire()
        self.sock.sendto(packet, self.get_partner())
        self.sock_send_lock.release()

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
        print(f"Set current sn to {sn}")

    def increase_current_sn(self):
        self.current_sn_lock.acquire()
        # TODO parametrisize rn max size
        self.current_sn = 1 + self.current_sn % 255
        print(f"Increased current sn to {self.current_sn}")
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
        print(f"Set current rn to {rn}")

    def increase_current_rn(self):
        self.current_rn_lock.acquire()
        self.current_rn = 1 + self.current_rn % 255
        print(f"Increased current rn to {self.current_rn}")
        self.current_rn_lock.release()

    def get_partner(self):
        return self.partner

    def deliver_packet(self, packet):
        self.receive_queue.put(packet)

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
