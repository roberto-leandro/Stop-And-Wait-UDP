from abc import ABC, abstractmethod
import utility
import random
import queue
"""
In order to handle the different states a connection might have at any given time, the State design pattern is used.
Each class in this module defines a state that can be held by the PseudoTCP connection, and implements its behavior on
the event of receiving a packet or a timeout.
"""
# TODO status classes for close, timeout handling for all statuses except ESTABLISHED


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
        is_syn = utility.are_flags_set(packet, utility.HEADER_SYN) and \
                 utility.are_flags_unset(packet, utility.HEADER_FIN | utility.HEADER_ACK)

        if not is_syn:
            print("Message received was not a proper SYN...")
            return

        print("The packet received was a valid SYN!")

        # Set the state variables to synchronize with the partner
        node.set_current_status(SynReceivedStatus())
        node.set_current_partner(origin_address)
        node.set_current_rn(utility.get_sn(packet))
        node.increase_current_rn()
        node.set_current_sn(random.randint(0, 255))

        # Send SYN-ACK
        syn_ack_message = utility.create_packet(syn=True, ack=True, sn=node.get_current_sn(), rn=node.get_current_rn())
        print(f"Sending SYN-ACK...")
        node.send_packet(syn_ack_message)

        # Store this packet in the send queue, in case it needs to be retransmitted later
        node.send_queue.put(syn_ack_message)

    @staticmethod
    def handle_timeout(node):
        # Do nothing
        print("Still listening for connections, do nothing...")


class SynReceivedStatus(State):
    STATUS_NAME = "SYN_RECEIVED"

    @staticmethod
    def handle_packet(packet, origin_address, node):
        is_ack = utility.are_flags_set(packet, utility.HEADER_ACK) \
                 and utility.get_sn(packet) == node.get_current_rn() \
                 and utility.get_rn(packet) != node.get_current_sn() \
                 and utility.are_flags_unset(packet, utility.HEADER_FIN, utility.HEADER_SYN)

        if not is_ack:
            print("Message received was not a proper ACK, retrying...")
            return

        # Remove the SYN-ACK packet from the send queue, not needed anymore
        node.send_queue.get()

        print("Message received was a proper ACK, connection established!!")
        # Update current variables: connection is now established
        node.set_current_status(EstablishedStatus())
        node.set_current_sn(utility.get_rn(packet))
        node.set_current_rn(utility.get_sn(packet))

    @staticmethod
    def handle_timeout(node):
        # Resend SYN-ACK, should be the next message in the send queue
        print("Resending SYN-ACK...")
        node.send_packet(node.peek_send_queue())


class SynSentStatus(State):
    STATUS_NAME = "SYN_SENT"

    @staticmethod
    def handle_packet(packet, origin_address, node):
        is_syn_ack = utility.are_flags_set(packet, utility.HEADER_SYN, utility.HEADER_ACK) \
                     and utility.get_rn(packet) != node.get_current_sn() \
                     and utility.are_flags_unset(packet, utility.HEADER_FIN)

        if not is_syn_ack:
            print("Message received was not a proper SYN-ACK, retrying...")
            return

        # Remove the SYN packet from the send queue, not needed anymore
        node.send_queue.get()

        print("Message received was a proper SYN-ACK, connection established!")
        # Update current variables: connection is now established, sn and rn should be flipped
        node.set_current_status(EstablishedStatus())
        node.set_current_sn(utility.get_rn(packet))
        node.set_current_rn(utility.get_sn(packet))
        node.increase_current_rn()

        # Send ACK
        ack_message = utility.create_packet(ack=True, sn=node.get_current_sn(), rn=node.get_current_rn())
        print(f"Sending ACK...")
        node.send_packet(ack_message)

        # TODO if this ACK is lost, its impossible to establish a connection

    @staticmethod
    def handle_timeout(node):
        # Resend SYN, should be the next message in the send queue
        print("Resending SYN...")
        node.send_packet(node.peek_send_queue())


class EstablishedStatus(State):
    STATUS_NAME = "ESTABLISHED"

    @staticmethod
    def handle_packet(packet, origin_address, node):
        is_valid = False
        # Parse the packet, determine if its valid and if an ACK should be sent
        # Check if packet contains new data
        if utility.get_sn(packet) == node.get_current_rn():
            is_valid = True
            print("Packet contains new data!")

            # Put the payload in the processed messages queue
            # First read the header to determine how many bytes are left
            data_left = packet[0] & utility.HEADER_DATA_LEFT
            if data_left == utility.HEADER_DATA_LEFT:
                # Write all the payload
                node.payload_queue.put(packet[utility.HEADER_SIZE:])
            else:
                # Write as many bytes as data_left indicates
                node.payload_queue.put(packet[utility.HEADER_SIZE:utility.HEADER_SIZE+data_left])

                # Write ASCII end of transmission
                node.payload_queue.put(0x4)

            # Increase rn
            node.increase_current_rn()

            # ACK the sender
            ack_message = utility.create_packet(ack=True, sn=node.get_current_sn(), rn=node.get_current_rn())
            print(f"Sending ACK...")
            node.send_packet(ack_message)

        # Check if packet contains an ACK
        if utility.are_flags_set(packet, utility.HEADER_ACK) and utility.get_rn(packet) != node.get_current_sn():
            print("Packet is an ACK!")
            is_valid = True
            # Pop the old latest packet
            try:
                old_packet = node.send_queue.get(block=False)
            except queue.Empty:
                print("Strange, an ACK was received even though the send queue is empty...")
                return

            print(f"Packet contains an ACK, which means the packet {utility.packet_to_string(old_packet)} has been sent"
                  f" successfully!")
            node.set_current_sn(utility.get_rn(packet))

            # Send next packet
            print("Sending next packet...")
            packet = None
            try:
                packet = node.peek_send_queue()
            except IndexError:
                print("Nothing to transmit...")

            if packet:
                node.send_packet(packet)

        if not is_valid:
            print(f"The SN in the packet was {utility.get_sn(packet)}, expected {node.get_current_rn()}. Ignoring...")

    @staticmethod
    def handle_timeout(node):
        # TODO this should also resend the latest ACK
        # Resend the next packet in the send queue
        print("Retransmitting latest packet...")
        packet = None

        if node.send_queue.empty():
            print("Nothing to retransmit...")
            return

        try:
            packet = node.peek_send_queue()
        except IndexError:
            print("Nothing to retransmit...")

        if packet:
            node.send_packet(packet)
