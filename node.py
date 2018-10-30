import socket
import utility
import threading
import random
import queue

import states
from pseudo_tcp import PseudoTCPSocket


class Node:
    def __init__(self, address):
        # Socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(address)

        # TODO add lock for this
        # Connections: a dict of pseudoTCP sockets indexed by ip-port pairs
        self.connections = {}

        # This class only has one state: accepting connection or not. All other states are handled by the sockets
        self.accepting_connections = False

        # Queues
        self.finished_messages_queue = queue.Queue()

        # Locks
        self.accepting_connections_lock = threading.Lock()
        self.sock_read_lock = threading.Lock()
        self.sock_send_lock = threading.Lock()

        # Stopper
        self.stopper = threading.Event()

        # Threads
        self.message_reader = threading.Thread(target=self.read_loop)
        self.message_reader.start()

    def connect(self, address):
        address = utility.resolve_localhost(address)

        if address not in self.connections:
            # Allocate resources for this new connection
            new_connection = PseudoTCPSocket(address, self.sock, self.sock_send_lock, self.finished_messages_queue)
            new_connection.initiate_connection()
            self.connections[address] = new_connection
        else:
            print("The connection already exists, please close it first!")

    def close(self, address):
        address = utility.resolve_localhost(address)

        print(f"Closing {address}...")
        # Check if the connection exists
        if address not in self.connections:
            print(f"Tried closing {address}, but that connection didn't exist!")
            return

        # Close the connection
        self.connections[address].close()

        # Remove the entry
        self.connections[address] = None
        print(f"Closed {address} successfully!")

    def close_all(self):
        print(f"Closing all connections...")

        for connection in self.connections:
            print(f"Closing {connection.get_partner()}...")
            connection.close()

        # Remove all entries
        self.connections = {}
        print(f"Closed all connections successfully!")

    def send(self, message, address):
        address = utility.resolve_localhost(address)

        print(f"Sending a message to {address}...")
        # Check if the connection exists
        if address not in self.connections:
            print(f"Tried sending a message to {address}, but that connection didn't exist!")
            return

        # Send the message
        self.connections[address].send(message)

    def recv(self, address):
        address = utility.resolve_localhost(address)

        print(f"Receiving a message from {address}...")
        # Lower level sockets assembled the payloads they receive from their partners into a high level message
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
           #     print("Oops! Dropped a packet...")

            # If a connection is established with this address, send the packet to that connection
            if address in self.connections:
                print(f"Routing packet to {address}")
                self.connections[address].receive_queue.put(packet)

            # Allocate resources to handle the new connection, if new connections are being accepted
            else:
                self.accepting_connections_lock.acquire()
                if self.accepting_connections:
                    print(f"Creating a new socket to handle incoming connection to {address}")
                    new_connection = PseudoTCPSocket(address, self.sock, self.sock_send_lock, self.finished_messages_queue)
                    new_connection.set_current_status(states.AcceptStatus)
                    new_connection.deliver_packet(packet)
                    self.connections[address] = new_connection
                self.accepting_connections_lock.release()

        print("Stopped read loop")

    def receive_packet(self):
        self.sock_read_lock.acquire()
        packet, address = self.sock.recvfrom(utility.PACKET_SIZE)
        self.sock_read_lock.release()

        print(f"Received packet {utility.packet_to_string(packet)} with SN={utility.get_sn(packet)} and "
              f"RN={utility.get_rn(packet)} and ACK={utility.are_flags_set(packet, utility.HEADER_ACK)} "
              f"from {address}")
        return packet, address
