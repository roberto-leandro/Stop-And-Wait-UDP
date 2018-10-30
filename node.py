import socket
import utility
import threading
import random
import queue

import states
from pseudo_tcp import PseudoTCPSocket


class Node:
    def __init__(self, address):
        address = utility.resolve_localhost(address)

        # Socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(address)

        # Logging
        self.log_filename = f"node_{address[0]}_{address[1]}.txt"

        # TODO add lock for this
        # Connections: a dict of pseudoTCP sockets indexed by ip-port pairs
        self.connections = {}

        # This class only has one state: accepting connection or not. All other states are handled by the sockets
        self.accepting_connections = False

        # Queues
        self.finished_messages_queue = queue.Queue()

        # Locks
        self.accepting_connections_lock = threading.Lock()
        self.log_file_lock = threading.Lock()
        self.sock_read_lock = threading.Lock()
        self.sock_send_lock = threading.Lock()

        # Stopper
        self.stopper = threading.Event()

        # Threads
        self.message_reader = threading.Thread(target=self.read_loop)
        self.message_reader.start()

        utility.log_message(f"Node has been started in {address}!")

    def connect(self, address):
        address = utility.resolve_localhost(address)

        if address not in self.connections:
            # Allocate resources for this new connection
            new_connection = PseudoTCPSocket(address, self.sock, self.sock_send_lock, self.finished_messages_queue, self.log_filename, self.log_file_lock)
            new_connection.initiate_connection()
            self.connections[address] = new_connection
        else:
            utility.log_message("The connection already exists, please close it first!", self.log_filename, self.log_file_lock)

    def close(self, address):
        address = utility.resolve_localhost(address)

        utility.log_message(f"Closing {address}...", self.log_filename, self.log_file_lock)
        # Check if the connection exists
        if address not in self.connections:
            utility.log_message(f"Tried closing {address}, but that connection didn't exist!", self.log_filename, self.log_file_lock)
            return

        # Close the connection
        self.connections[address].close()

        # Remove the entry
        self.connections[address] = None
        utility.log_message(f"Closed {address} successfully!", self.log_filename, self.log_file_lock)

    def close_all(self):
        utility.log_message(f"Closing all connections...", self.log_filename, self.log_file_lock)

        for address, connection in self.connections.items():
            utility.log_message(f"Closing {address}...", self.log_filename, self.log_file_lock)
            connection.close()

        # Remove all entries
        self.connections = {}
        utility.log_message(f"Closed all connections successfully!", self.log_filename, self.log_file_lock)

    def send(self, message, address):
        address = utility.resolve_localhost(address)

        utility.log_message(f"Sending a message to {address}...", self.log_filename, self.log_file_lock)
        # Check if the connection exists
        if address not in self.connections:
            utility.log_message(f"Tried sending a message to {address}, but that connection didn't exist!", self.log_filename, self.log_file_lock)
            return

        # Send the message
        self.connections[address].send(message)

    def recv(self):
        # Lower level sockets assemble the payloads they receive from their partners into a high level message
        # Those messages are placed in the finished_message_queue shared among all connections
        return self.finished_messages_queue.get(block=True)

    def set_accepting_connections(self, value):
        self.accepting_connections_lock.acquire()
        self.accepting_connections = value
        self.accepting_connections_lock.release()

    def read_loop(self):
        """Puts packets in the receive queue"""
        while not self.stopper.is_set():
            # FIXME: receive_packets recvfrom call blocks
            packet, address = self.receive_packet()

            # Randomly drop some packets to test the Stop-And-Wait algorithm
           # if random.randint(1, 10) == 1:
           #     utility.log_message("Oops! Dropped a packet...", self.log_filename, self.log_file_lock)

            # If a connection is established with this address, send the packet to that connection
            if address in self.connections:
                utility.log_message(f"Routing packet to {address}", self.log_filename, self.log_file_lock)
                self.connections[address].receive_queue.put(packet)

            # Allocate resources to handle the new connection, if new connections are being accepted
            else:
                self.accepting_connections_lock.acquire()
                if self.accepting_connections:
                    utility.log_message(f"Creating a new socket to handle incoming connection to {address}", self.log_filename, self.log_file_lock)
                    new_connection = PseudoTCPSocket(address, self.sock, self.sock_send_lock, self.finished_messages_queue, self.log_filename, self.log_file_lock)
                    new_connection.set_current_status(states.AcceptStatus)
                    new_connection.deliver_packet(packet)
                    self.connections[address] = new_connection
                self.accepting_connections_lock.release()

        utility.log_message("Stopped read loop", self.log_filename, self.log_file_lock)

    def receive_packet(self):
        self.sock_read_lock.acquire()
        packet, address = self.sock.recvfrom(utility.PACKET_SIZE)
        self.sock_read_lock.release()

        utility.log_message(f"Received packet {utility.packet_to_string(packet)} with SN={utility.get_sn(packet)} and "
              f"RN={utility.get_rn(packet)} and ACK={utility.are_flags_set(packet, utility.HEADER_ACK)} "
              f"from {address}", self.log_filename, self.log_file_lock)
        return packet, address
