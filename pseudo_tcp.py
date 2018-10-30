import random
import queue
import threading
import states
import utility


class PseudoTCPSocket:

    # TODO the message does not start being sent when send() is called, instead it starts after a timeout
    # TODO pick a good timeout
    def __init__(self, address, sock, sock_lock, finished_message_queue, closed_connections_queue, log_filename, log_file_lock):
        # Change localhost to 127.0.0.1 from now so the address can be written as the current partner
        if address[0] == 'localhost':
            address = ('127.0.0.1', address[1])

        # TODO remove
        self.times_notified = 0
        self.times_unblocked = 0

        # Logging
        self.log_filename = log_filename

        # Socket
        self.sock = sock

        # State variables
        self.current_status = states.ClosedStatus()
        self.current_sn = 0
        self.current_rn = 0
        self.partner = address

        # Queues used only in this socket
        self.send_queue = queue.Queue()
        self.receive_queue = queue.Queue()
        self.payload_queue = queue.Queue()

        # Queues shared among all connection
        self.finished_message_queue = finished_message_queue
        self.closed_connections_queue = closed_connections_queue

        # Locks used only in this socket
        self.sock_read_lock = threading.Lock()
        self.send_queue_lock = threading.Lock()
        self.current_status_lock = threading.Lock()
        self.current_sn_lock = threading.Lock()
        self.current_rn_lock = threading.Lock()

        # Locks shared among all connection
        self.sock_send_lock = sock_lock
        self.log_file_lock = log_file_lock

        # Events
        self.terminate_socket_event = threading.Event()

        # Threads
        self.handler_thread = threading.Thread(target=self.main_loop)
        self.handler_thread.start()
        self.message_assembly_thread = threading.Thread(target=self.assemble_message_loop)
        self.message_assembly_thread.start()

        utility.log_message(f"Socket for {address} has been started!", self.log_filename, self.log_file_lock)

    def initiate_connection(self):
        utility.log_message(f"Trying to connect to {self.partner}...", self.log_filename, self.log_file_lock)

        # Build the SYN message, choosing a random value for sn
        self.set_current_sn(random.randint(0, 255))
        syn_message = utility.create_packet(syn=True, sn=self.get_current_sn())
        # Send SYN
        utility.log_message(f"Sending SYN...", self.log_filename, self.log_file_lock)
        self.send_packet(syn_message)
        self.set_current_status(states.SynSentStatus())

        # Send SYN is the send_queue, as it might need to be resent if the packet is lost
        self.send_queue.put(syn_message)

    def terminate_socket(self):
        # Set the termination event so all other threads in this sockets can finish
        self.terminate_socket_event.set()

        # Put a message in the payload_queue so message_assembler wakes up
        self.payload_queue.put(0x5)

        # Wait for the threads to finish
        self.message_assembly_thread.join()

        # Add this connection's address to the termination queue, so the node may delete the entry
        self.closed_connections_queue.put(self.partner)

    def main_loop(self):
        """This loop will handle the three main events: receiving data from an upper layer, receiving an ack, or a
        timeout"""
        while not self.terminate_socket_event.is_set():
            try:
                # This call blocks until an element is available
                packet = self.receive_queue.get(block=True, timeout=utility.TIMEOUT)
                self.receive_queue.task_done()
            except queue.Empty:
                # Timed out waiting for a packet
                utility.log_message(f"Timeout! Handling with current status {self.get_current_status().STATUS_NAME}", self.log_filename, self.log_file_lock)
                self.get_current_status().handle_timeout(self)
                continue

            utility.log_message(f"Handling received packet with current status {self.get_current_status().STATUS_NAME}", self.log_filename, self.log_file_lock)
            self.get_current_status().handle_packet(packet=packet, node=self)
        utility.log_message("Main loop finished!", self.log_filename, self.log_file_lock)

    def assemble_message_loop(self):
        """Assemble the payload fragments into a message, and send it to upper layer"""
        message = bytearray()
        received_bytes = 0
        # Read until end of transmission
        while True:
            current_payload = None
            try:
                current_payload = self.payload_queue.get(block=True)
            except queue.Empty:
                # Whether queue was empty or not, a check to self.terminate_socket_event must be performed either way
                pass

            if self.terminate_socket_event.is_set():
                break

            if current_payload == 0x4:
                self.payload_queue.task_done()
                # Message ended, put it in the finished_message_queue and reset variables
                utility.log_message(f"Finished reading the message {message}!", self.log_filename, self.log_file_lock)
                self.finished_message_queue.put(message, self.partner)
                message = bytearray()
                received_bytes = 0

            elif current_payload != 0x5:
                # Add the next payload to the message
                message[received_bytes:utility.PAYLOAD_SIZE:] = current_payload
                received_bytes += utility.PAYLOAD_SIZE

        utility.log_message("Assemble message loop finished!", self.log_filename, self.log_file_lock)

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
        # Block until all tasks in the queues are done
        self.send_queue.join()
        self.receive_queue.join()

        utility.log_message(f"Close {self.partner}, sending FIN...", self.log_filename, self.log_file_lock)
        close_packet = utility.create_packet(fin=True)
        self.increase_current_sn()
        self.send_packet(close_packet)
        self.send_queue.put(close_packet)
        self.set_current_status(states.FinSentStatus)

    def peek_send_queue(self):
        with self.send_queue.mutex:
            first_packet = self.send_queue.queue[0]
        return first_packet

    def send_packet(self, packet):
        # Write RN and SN
        packet[1] = self.get_current_rn()
        packet[2] = self.get_current_sn()

        utility.log_message(f"Sending packet {utility.packet_to_string(packet)} with SN={utility.get_sn(packet)} and "
                            f"RN={utility.get_rn(packet)} and ACK={utility.are_flags_set(packet, utility.HEADER_ACK)} to "
                            f"{self.get_partner()}", self.log_filename, self.log_file_lock)

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
        utility.log_message(f"Set current sn to {sn}", self.log_filename, self.log_file_lock)

    def increase_current_sn(self):
        self.current_sn_lock.acquire()
        self.current_sn = 1 + self.current_sn % 255
        utility.log_message(f"Increased current sn to {self.current_sn}", self.log_filename, self.log_file_lock)
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
        utility.log_message(f"Set current rn to {rn}", self.log_filename, self.log_file_lock)

    def increase_current_rn(self):
        self.current_rn_lock.acquire()
        self.current_rn = 1 + self.current_rn % 255
        utility.log_message(f"Increased current rn to {self.current_rn}", self.log_filename, self.log_file_lock)
        self.current_rn_lock.release()

    def get_partner(self):
        return self.partner

    def deliver_packet(self, packet):
        self.receive_queue.put(packet)

    def get_current_status(self):
        status = None
        self.current_status_lock.acquire()
        old_status = self.current_status.STATUS_NAME
        status = self.current_status
        if old_status != self.current_status.STATUS_NAME:
            utility.log_message(f"Changed status from {old_status} to {self.current_status.STATUS_NAME}!",
                                self.log_filename, self.log_file_lock)
        self.current_status_lock.release()
        return status

    def set_current_status(self, new_status):
        self.current_status_lock.acquire()
        self.current_status = new_status
        self.current_status_lock.release()
