import socket


class PseudoTCPNode:
    PACKET_SIZE = 1
    SOCKET_TIMEOUT = 50

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(self.SOCKET_TIMEOUT)

    def bind(self, address):
        self.sock.bind(address)

    def accept(self):
        pass

    def recv(self):
        pass

    def connect(self, address):
        # Instantiate a socket to send the data
        new_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        while True:
            # Send SYN
            new_socket.sendall(self.HEADER_SYN)

            # Wait for SYN-ACK
            syn_ack = new_socket.recv(1)

            # If nothing was received, try again
            if not syn_ack:
                break



        # Send ACK
        pass

    def send(self):
        pass
