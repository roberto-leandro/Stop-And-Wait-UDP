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

        # Connections: a dict of pseudoTCP sockets indexed by ip-port pairs
        self.connections = {}

        # This class only has one state: accepting connection or not. All other states are handled by the sockets
        self.accepting_connections = False

        # Queues
        self.finished_messages_queue = queue.Queue()
        self.closed_connections_queue = queue.Queue()

        # Locks
        self.accepting_connections_lock = threading.RLock()  # Reentrant to support close_node()'s logic
        self.connections_lock = threading.Lock()
        self.log_file_lock = threading.Lock()
        self.sock_read_lock = threading.Lock()
        self.sock_send_lock = threading.Lock()

        # Events
        self.terminate_node_event = threading.Event()

        # Threads
        self.message_reader = threading.Thread(target=self.read_loop)
        self.message_reader.start()
        self.connection_killer = threading.Thread(target=self.close_connections_loop)
        self.connection_killer.start()

        utility.log_message(f"Node has been started in {address}!", self.log_filename, self.log_file_lock)

    def connect(self, address):
        address = utility.resolve_localhost(address)
        self.connections_lock.acquire()

        if address not in self.connections:
            # Allocate resources for this new connection
            new_connection = PseudoTCPSocket(address, self.sock, self.sock_send_lock, self.finished_messages_queue,
                                             self.closed_connections_queue, self.log_filename, self.log_file_lock)
            new_connection.initiate_connection()
            self.connections[address] = new_connection
        else:
            utility.log_message("The connection already exists, please close it first!", self.log_filename, self.log_file_lock)
        self.connections_lock.release()

    def close_connection(self, address):
        """
        Closes one connection in the connections table-
        :param address: the ip-port pair of the connection to be closed and deleted.
        """
        address = utility.resolve_localhost(address)
        utility.log_message(f"Closing {address}, will wait until its operations are complete...", self.log_filename, self.log_file_lock)

        # Check if the connection exists
        self.connections_lock.acquire()
        if address not in self.connections:
            utility.log_message(f"Tried closing {address}, but that connection didn't exist!", self.log_filename, self.log_file_lock)
            return

        # Close the connection
        self.connections[address].close()
        self.connections_lock.release()

    def close_all_connections(self):
        """
        Closes all current connections. The node will not be closed.
        """
        utility.log_message(f"Closing all connections, will wait until all operations are complete...", self.log_filename, self.log_file_lock)
        self.accepting_connections_lock.acquire()
        old_value = self.accepting_connections
        self.accepting_connections = False
        self.connections_lock.acquire()

        for address, connection in self.connections.items():
            connection.close()

        # Release locks
        self.accepting_connections = old_value
        self.accepting_connections_lock.release()
        self.connections_lock.release()

    def close_node(self):
        """
        Closes all connections and terminates this node.
        """
        self.accepting_connections_lock.acquire()
        self.accepting_connections = False

        # Close all current connections
        self.close_all_connections()

        # Set the event for node termination
        self.terminate_node_event.set()

        # Wait for threads to finish
        self.message_reader.join()
        self.connection_killer.join()

    def send(self, message, address):
        address = utility.resolve_localhost(address)

        utility.log_message(f"Sending a message to {address}...", self.log_filename, self.log_file_lock)
        # Check if the connection exists
        self.connections_lock.acquire()
        if address not in self.connections:
            utility.log_message(f"Tried sending a message to {address}, but that connection didn't exist!", self.log_filename, self.log_file_lock)
            return

        # Send the message
        self.connections[address].send(message)
        self.connections_lock.release()

    def recv(self):
        # Lower level sockets assemble the payloads they receive from their partners into a high level message
        # Those messages are placed in the finished_message_queue shared among all connections
        message = self.finished_messages_queue.get(block=True)
        self.finished_messages_queue.task_done()
        return message

    def set_accepting_connections(self, value):
        self.accepting_connections_lock.acquire()
        self.accepting_connections = value
        self.accepting_connections_lock.release()

    def read_loop(self):
        """Puts packets in the receive queue"""
        while not self.terminate_node_event.is_set():
            # FIXME: receive_packets recvfrom call blocks
            packet, address = self.receive_packet()

            # Randomly drop some packets to test the Stop-And-Wait algorithm
            # TODO uncomment this
           # if random.randint(1, 10) == 1:
           #     utility.log_message("Oops! Dropped a packet...", self.log_filename, self.log_file_lock)

            # If a connection is established with this address, send the packet to that connection
            self.connections_lock.acquire()
            if address in self.connections:
                utility.log_message(f"Routing packet to {address}", self.log_filename, self.log_file_lock)
                self.connections[address].receive_queue.put(packet)

            # If new connections are being accepted and the incoming message indicates it want ot initiate a connection
            # Allocate resources for the connection
            elif utility.are_flags_set(packet, utility.HEADER_SYN):
                self.accepting_connections_lock.acquire()
                if self.accepting_connections:
                    utility.log_message(f"Creating a new socket to handle incoming connection to {address}", self.log_filename, self.log_file_lock)
                    new_connection = PseudoTCPSocket(address, self.sock, self.sock_send_lock,
                                                     self.finished_messages_queue, self.closed_connections_queue,
                                                     self.log_filename, self.log_file_lock)
                    new_connection.set_current_status(states.AcceptStatus)
                    new_connection.deliver_packet(packet)
                    self.connections[address] = new_connection
                else:
                    utility.log_message(f"{address} wanted to initiate a connection, but the node is not accepting "
                                        f"connections. Ignoring...", self.log_filename, self.log_file_lock)

                self.accepting_connections_lock.release()

            else:
                utility.log_message(f"The message from {address} didn't have an open connection and didn't contain a "
                                    f"SYN, ignoring...", self.log_filename, self.log_file_lock)
            self.connections_lock.release()
        utility.log_message("Read loop finished!", self.log_filename, self.log_file_lock)

    def close_connections_loop(self):
        """
        Whenever a connection is going to teminate, it should signal this thread to remove its entry in the connections
        table.
        """
        while not self.terminate_node_event.is_set():
            # Block until a socket is terminated, and delete that entry
            # FIXME busy waiting
            try:
                terminated_address = self.closed_connections_queue.get(block=False)
            except queue.Empty:
                continue
            self.connections_lock.acquire()
            del self.connections[terminated_address]
            utility.log_message(f"Closed {terminated_address} successfully!", self.log_filename, self.log_file_lock)
            self.connections_lock.release()


    def receive_packet(self):
        self.sock_read_lock.acquire()
        packet, address = self.sock.recvfrom(utility.PACKET_SIZE)
        self.sock_read_lock.release()

        utility.log_message(f"Received packet {utility.packet_to_string(packet)} with SN={utility.get_sn(packet)} and "
              f"RN={utility.get_rn(packet)} and ACK={utility.are_flags_set(packet, utility.HEADER_ACK)} "
              f"from {address}", self.log_filename, self.log_file_lock)
        return packet, address
