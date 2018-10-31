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
    def handle_packet(packet, node):
        pass


class ClosedStatus(State):
    STATUS_NAME = "CLOSED"

    @staticmethod
    def handle_packet(packet, node):
        # Do nothing
        print("No connection is established, doing nothing...")

    @staticmethod
    def handle_timeout(node):
        # Do nothing
        print("No connection is established, doing nothing...")


class AcceptStatus(State):
    STATUS_NAME = "ACCEPT"

    @staticmethod
    def handle_packet(packet, node):
        # Check if message contains a valid SYN
        is_syn = utility.are_flags_set(packet, utility.HEADER_SYN) and \
                 utility.are_flags_unset(packet, utility.HEADER_FIN | utility.HEADER_ACK)

        if not is_syn:
            print("Message received was not a proper SYN...")
            return

        print("The packet received was a valid SYN!")

        # Set the state variables to synchronize with the partner
        node.set_current_status(SynReceivedStatus())
        node.set_current_rn(utility.get_sn(packet))
        node.increase_current_rn()
        node.set_current_sn(random.randint(0, 255))

        # Send SYN-ACK
        syn_ack_message = utility.create_packet(syn=True, ack=True, sn=node.get_current_sn(), rn=node.get_current_rn())
        print(f"Sending SYN-ACK...")
        node.send_packet(syn_ack_message)

    @staticmethod
    def handle_timeout(node):
        # Do nothing
        print("Still listening for connections, do nothing...")


class SynReceivedStatus(State):
    STATUS_NAME = "SYN_RECEIVED"

    @staticmethod
    def handle_packet(packet, node):
        is_ack = utility.are_flags_set(packet, utility.HEADER_ACK) \
                 and utility.get_sn(packet) == node.get_current_rn() \
                 and utility.get_rn(packet) != node.get_current_sn() \
                 and utility.are_flags_unset(packet, utility.HEADER_FIN, utility.HEADER_SYN)

        if not is_ack:
            print("Message received was not a proper ACK, retrying...")
            return

        print("Message received was a proper ACK, connection established!!")
        # Update current variables: connection is now established
        node.set_current_status(EstablishedStatus())
        node.set_current_rn(utility.get_sn(packet))

        # This packet might contain data, as the connection is now established it should be managed as such
        EstablishedStatus.handle_packet(packet, node)

    @staticmethod
    def handle_timeout(node):
        # Resend SYN-ACK
        print("Resending SYN-ACK...")
        last_sent_packet = node.get_last_sent_packet()
        if last_sent_packet is not None:
            node.send_packet(last_sent_packet)
        else:
            print("Nothing to retransmit...")


class SynSentStatus(State):
    STATUS_NAME = "SYN_SENT"

    @staticmethod
    def handle_packet(packet, node):
        is_syn_ack = utility.are_flags_set(packet, utility.HEADER_SYN, utility.HEADER_ACK) \
                     and utility.get_rn(packet) != node.get_current_sn() \
                     and utility.are_flags_unset(packet, utility.HEADER_FIN)

        if not is_syn_ack:
            print("Message received was not a proper SYN-ACK, retrying...")
            return

        print("Message received was a proper SYN-ACK, connection established!")
        # Update current variables: connection is now established, sn and rn should be increased
        node.set_current_status(EstablishedStatus())
        node.set_current_sn(utility.get_rn(packet))
        node.set_current_rn(utility.get_sn(packet))
        node.increase_current_rn()

        # Send ACK, if data is available include it
        try:
            # Get next packet
            ack_message = node.send_queue.get(block=False)
            node.send_queue.task_done()
            # Turn ack on
            ack_message[0] = ack_message[0] | utility.HEADER_ACK
            print(f"Sending ACK with a payload...")
        except queue.Empty:
            ack_message = utility.create_packet(ack=True, sn=node.get_current_sn(), rn=node.get_current_rn())
            print(f"Sending ACK without a payload...")
        node.send_packet(ack_message)

    @staticmethod
    def handle_timeout(node):
        # Resend SYN, should be the next message in the send queue
        print("Resending SYN...")
        last_sent_packet = node.get_last_sent_packet()
        if last_sent_packet is not None:
            node.send_packet(last_sent_packet)
        else:
            print("Nothing to retransmit...")


class EstablishedStatus(State):
    STATUS_NAME = "ESTABLISHED"

    @staticmethod
    def handle_packet(packet, node):
        is_valid = False
        if utility.are_flags_set(packet, utility.HEADER_FIN):
            is_valid = True
            print("Received a FIN! Sending FIN-ACK...")
            fin_ack_packet = utility.create_packet(fin=True, ack=True)
            node.send_packet(fin_ack_packet)

            print("Terminating this socket...")
            node.terminate_socket(notify_connections_remover=True)
            return

        reply_message = None

        # Parse the packet, determine if its valid and if an ACK should be sent
        # First check if packet contains an ACK
        if utility.are_flags_set(packet, utility.HEADER_ACK) and utility.get_rn(packet) > node.get_current_sn():
            is_valid = True
            if node.last_sent_packet is not None:
                print(f"Packet contains an ACK, which means the packet "
                      f"{utility.packet_to_string(node.last_sent_packet)} has been sent successfully!")
            node.set_last_sent_packet(None)
            node.set_current_sn(utility.get_rn(packet))

            # Send next packet
            print("Adding next packet to reply...")
            try:
                reply_message = node.send_queue.get(block=False)
                node.send_queue.task_done()
            except queue.Empty:
                print("Nothing to transmit...")
        elif utility.are_flags_set(packet, utility.HEADER_ACK):
            print(f"Packet has ACK turned on, but its RN was {utility.get_rn(packet)} and expected was "
                  f"{node.get_current_sn()+1}")

        # Then, check if packet contains new data
        data_left = packet[0] & utility.HEADER_DATA_LEFT
        if utility.get_sn(packet) == node.get_current_rn() and data_left != 0:
            is_valid = True
            print("Packet contains new data!")

            # Put the payload in the processed messages queue
            # First read the header to determine how many bytes are left
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

            # Add an ACK to the reply
            print("Adding an ACK to reply...")
            if reply_message is None:
                reply_message = utility.create_packet(ack=True)
            else:
                reply_message[0] = reply_message[0] | utility.HEADER_ACK

        elif data_left != 0 and utility.get_sn(packet) == node.get_current_rn():
            print(f"Packet contained a payload but its sn was {utility.get_sn(packet)} and expected is {node.get_current_rn()}")

        if reply_message is not None:
            print("Sending reply...")
            node.send_packet(reply_message)
        elif not is_valid:
            print("Packet was neither an ACK nor contained new data, ignoring...")

    @staticmethod
    def handle_timeout(node):
        # Resend the next packet in the send queue
        print("Retransmitting latest packet...")
        last_sent_packet = node.get_last_sent_packet()
        if last_sent_packet is not None:
            # If the latest packet has no payload and there is now one available, add it.
            if last_sent_packet[0] & utility.HEADER_DATA_LEFT == 0:
                try:
                    next_message = node.send_queue.get(block=False)
                    node.send_queue.task_done()
                    next_message[0] = next_message[0] | last_sent_packet[0]
                    last_sent_packet = next_message
                except queue.Empty:
                    pass

            node.send_packet(last_sent_packet)
        else:
            try:
                node.send_packet(node.send_queue.get(block=False))
                node.send_queue.task_done()
            except queue.Empty:
                print("Nothing to transmit.")


class FinSentStatus(State):
    STATUS_NAME = "FIN_SENT"

    @staticmethod
    def handle_packet(packet, node):
        is_valid_fin_ack = utility.are_flags_set(packet, utility.HEADER_ACK, utility.HEADER_FIN) \
                       and utility.get_rn(packet) != node.get_current_sn() \
                       and utility.are_flags_unset(packet, utility.HEADER_SYN)

        if not is_valid_fin_ack:
            print("Message received was not a proper FIN-ACK, retrying...")
            return

        print("Message received was a proper FIN-ACK, terminating this socket...")
        node.terminate_socket(notify_connections_remover=False)

    @staticmethod
    def handle_timeout(node):
        # Resend FIN, should be the next message in the send queue
        print("Resending FIN...")
        last_sent_packet = node.get_last_sent_packet()
        if last_sent_packet is not None:
            node.send_packet(last_sent_packet)
        else:
            print("Nothing to retransmit...")

