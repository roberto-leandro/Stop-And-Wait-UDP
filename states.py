from abc import ABC, abstractmethod
import utility
import random
import queue
"""
In order to handle the different states a connection might have at any given time, the State design pattern is used.
Each class in this module defines a state that can be held by the PseudoTCP connection, and implements its behavior on
the event of receiving a packet or a timeout.
"""


class State(ABC):
    STATUS_NAME = None

    @staticmethod
    @abstractmethod
    def handle_timeout(node):
        pass

    @staticmethod
    @abstractmethod
    def handle_packet(packet, origin_address, node):
        pass


class ClosedStatus(State):
    STATUS_NAME = "CLOSED"

    @staticmethod
    def handle_packet(packet, origin_address, node):
        # Do nothing
        print("No connection is established, doing nothing...")

    @staticmethod
    def handle_timeout(node):
        # Do nothing
        print("No connection is established, doing nothing...")


class AcceptStatus(State):
    STATUS_NAME = "ACCEPT"

    @staticmethod
    def handle_packet(packet, origin_address, node):
        # Check if message contains a valid SYN
        header = packet[0]
        is_syn = utility.are_flags_set(header, utility.HEADER_SYN) and \
                 utility.are_flags_unset(header, utility.HEADER_FIN | utility.HEADER_ACK)

        if not is_syn:
            print("Message received was not a proper SYN...")
            return

        print("The packet received was a valid SYN!")

        # Set the state variables to synchronize with the partner
        node.set_current_status(SynReceivedStatus())
        node.set_current_partner(origin_address)
        node.flip_current_rn()
        node.set_current_sn(random.choice([True, False]))

        # Send SYN-ACK
        syn_ack_message = utility.create_packet(syn=True, ack=True, sn=node.get_current_sn(), rn=node.get_current_rn())
        print(f"Sending {utility.packet_to_string(syn_ack_message)} to {origin_address}")
        node.send_packet(syn_ack_message)

    @staticmethod
    def handle_timeout(node):
        pass


class SynReceivedStatus(State):
    STATUS_NAME = "SYN_RECEIVED"

    @staticmethod
    def handle_packet(packet, origin_address, node):
        header = packet[0]
        is_ack = utility.are_flags_set(header, utility.HEADER_ACK) \
                 and utility.get_sn(header) == node.get_current_rn() \
                 and utility.get_rn(header) != node.get_current_sn() \
                 and utility.are_flags_unset(header, utility.HEADER_FIN, utility.HEADER_SYN)

        if not is_ack:
            print("Message received was not a proper ACK, retrying...")
            return

        print("Message received was a proper ACK, connection established!!")
        # Update current variables: connection is now established, sn and rn should be flipped
        node.set_current_status(EstablishedStatus())
        node.set_current_sn(utility.get_rn(header))
        node.set_current_rn = not utility.get_sn(header)

    @staticmethod
    def handle_timeout(node):
        pass


class SynSentStatus(State):
    STATUS_NAME = "SYN_SENT"

    @staticmethod
    def handle_packet(packet, origin_address, node):
        header = packet[0]
        is_syn_ack = utility.are_flags_set(header, utility.HEADER_SYN, utility.HEADER_ACK) \
                     and utility.get_rn(header) != node.get_current_sn() \
                     and utility.are_flags_unset(header, utility.HEADER_FIN)

        if not is_syn_ack:
            print("Message received was not a proper SYN-ACK, retrying...")
            return

        print("Message received was a proper SYN-ACK, connection established!")
        # Update current variables: connection is now established, sn and rn should be flipped
        node._set_current_status(EstablishedStatus())
        node.set_current_sn(utility.get_rn(header))
        node.set_current_rn(not utility.get_sn(header))

        # Send ACK
        ack_message = utility.create_packet(ack=True, sn=node.get_current_sn(), rn=node.get_current_sn())
        print(f"Sending ACK {utility.packet_to_string(ack_message)}")
        node.send_packet(ack_message)

    @staticmethod
    def handle_timeout(node):
        pass


class EstablishedStatus(State):
    STATUS_NAME = "ESTABLISHED"

    @staticmethod
    def handle_packet(packet, origin_address, node):
        is_valid = False
        header = packet[0]
        # Parse the packet, determine if its valid and if an ACK should be sent
        # Check if packet contains new data
        if utility.get_sn(header) == node.get_current_rn():
            is_valid = True
            print("Packet contains new data!")

            # Put the payload in the proccessed messages queue
            node.payload_queue.put(packet[utility.HEADER_SIZE:])

            # Increase rn
            node.current_rn = not node.get_current_rn()

            # ACK the sender
            ack_message = utility.create_packet(ack=True, sn=node.get_current_sn(), rn=node.get_current_rn())
            print(f"Sending ACK {utility.packet_to_string(ack_message)}")
            node.send_packet(ack_message)

        # Check if packet contains an ACK
        if utility.are_flags_set(header, utility.HEADER_ACK) and utility.get_rn(header) != node.get_current_sn():
            is_valid = True
            print("Packet contains an ACK!")
            node.set_current_sn(utility.get_rn(header))

            # Send next packet
            # TODO add locks
            print("Sending next packet...")
            # TODO get from the queue without removing the packet, as it might need to be retransmitted if its lost
            packet = None
            try:
                packet = node.send_queue.get(block=False)
            except queue.Empty:
                print("Nothing to transmit...")

            if packet:
                print(f"The next packet is {utility.packet_to_string(packet)}, sending to {node.get_current_partner()}...")
                node.sock_packet(packet)

        if not is_valid:
            print(f"The SN in the packet was {utility.get_sn(header)}, expected {node.get_current_rn()}...")

    @staticmethod
    def handle_timeout(node):
        # Resend the next packet in the send queue
        print("Retransmitting latest packet...")
        # TODO get from the queue without removing the packet, as it might need to be retransmitted if its lost
        packet = None
        try:
            packet = node.send_queue.get(block=False)
        except queue.Empty:
            print("Nothing to retransmit...")

        if packet:
            print(f"The latest packet is {utility.packet_to_string(packet)}, sending to {node.current_partner}...")
            node.send_packet(packet)


