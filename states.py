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
    def handle_timeout(pseudo_sock):
        pass

    @staticmethod
    @abstractmethod
    def handle_packet(packet, pseudo_sock):
        pass


class ClosedStatus(State):
    STATUS_NAME = "CLOSED"

    @staticmethod
    def handle_packet(packet, pseudo_sock):
        # Do nothing
        utility.log_message("No connection is established, doing nothing...", pseudo_sock.log_filename, pseudo_sock.log_file_lock)

    @staticmethod
    def handle_timeout(pseudo_sock):
        # Do nothing
        utility.log_message("No connection is established, doing nothing...", pseudo_sock.log_filename, pseudo_sock.log_file_lock)


class AcceptStatus(State):
    STATUS_NAME = "ACCEPT"

    @staticmethod
    def handle_packet(packet, pseudo_sock):
        # Check if message contains a valid SYN
        is_syn = utility.are_flags_set(packet, utility.HEADER_SYN) and \
                 utility.are_flags_unset(packet, utility.HEADER_FIN | utility.HEADER_ACK)

        if not is_syn:
            utility.log_message("Message received was not a proper SYN...", pseudo_sock.log_filename, pseudo_sock.log_file_lock)
            return

        utility.log_message("The packet received was a valid SYN!", pseudo_sock.log_filename, pseudo_sock.log_file_lock)

        # Set the state variables to synchronize with the partner
        pseudo_sock.set_current_status(SynReceivedStatus())
        pseudo_sock.set_current_rn(utility.get_sn(packet))
        pseudo_sock.increase_current_rn()
        pseudo_sock.set_current_sn(random.randint(0, 255))

        # Send SYN-ACK
        syn_ack_message = utility.create_packet(syn=True, ack=True, sn=pseudo_sock.get_current_sn(), rn=pseudo_sock.get_current_rn())
        utility.log_message(f"Sending SYN-ACK...", pseudo_sock.log_filename, pseudo_sock.log_file_lock)
        pseudo_sock.send_packet(syn_ack_message)

    @staticmethod
    def handle_timeout(pseudo_sock):
        # Do nothing
        utility.log_message("Still listening for connections, do nothing...", pseudo_sock.log_filename, pseudo_sock.log_file_lock)


class SynReceivedStatus(State):
    STATUS_NAME = "SYN_RECEIVED"

    @staticmethod
    def handle_packet(packet, pseudo_sock):
        is_ack = utility.are_flags_set(packet, utility.HEADER_ACK) \
                 and utility.get_sn(packet) == pseudo_sock.get_current_rn() \
                 and utility.get_rn(packet) != pseudo_sock.get_current_sn() \
                 and utility.are_flags_unset(packet, utility.HEADER_FIN, utility.HEADER_SYN)

        if not is_ack:
            utility.log_message("Message received was not a proper ACK, retrying...", pseudo_sock.log_filename,
                                pseudo_sock.log_file_lock)
            return

        utility.log_message("Message received was a proper ACK, connection established!!", pseudo_sock.log_filename,
                            pseudo_sock.log_file_lock)
        # Update current variables: connection is now established
        pseudo_sock.set_current_status(EstablishedStatus())
        pseudo_sock.set_current_rn(utility.get_sn(packet))

        # This packet might contain data, as the connection is now established it should be managed as such
        EstablishedStatus.handle_packet(packet, pseudo_sock)

    @staticmethod
    def handle_timeout(pseudo_sock):
        # Resend SYN-ACK
        utility.log_message("Resending SYN-ACK...", pseudo_sock.log_filename, pseudo_sock.log_file_lock)
        last_sent_packet = pseudo_sock.get_last_sent_packet()
        if last_sent_packet is not None:
            pseudo_sock.send_packet(last_sent_packet)
        else:
            utility.log_message("Nothing to retransmit...", pseudo_sock.log_filename, pseudo_sock.log_file_lock)


class SynSentStatus(State):
    STATUS_NAME = "SYN_SENT"

    @staticmethod
    def handle_packet(packet, pseudo_sock):
        is_syn_ack = utility.are_flags_set(packet, utility.HEADER_SYN, utility.HEADER_ACK) \
                     and utility.get_rn(packet) != pseudo_sock.get_current_sn() \
                     and utility.are_flags_unset(packet, utility.HEADER_FIN)

        if not is_syn_ack:
            utility.log_message("Message received was not a proper SYN-ACK, retrying...", pseudo_sock.log_filename,
                                pseudo_sock.log_file_lock)
            return

        utility.log_message("Message received was a proper SYN-ACK, connection established!", pseudo_sock.log_filename,
                            pseudo_sock.log_file_lock)
        # Update current variables: connection is now established, sn and rn should be increased
        pseudo_sock.set_current_status(EstablishedStatus())
        pseudo_sock.set_current_sn(utility.get_rn(packet))
        pseudo_sock.set_current_rn(utility.get_sn(packet))
        pseudo_sock.increase_current_rn()

        # Send ACK, if data is available include it
        try:
            # Get next packet
            ack_message = pseudo_sock.send_queue.get(block=False)
            pseudo_sock.send_queue.task_done()
            # Turn ack on
            ack_message[0] = ack_message[0] | utility.HEADER_ACK
            utility.log_message(f"Sending ACK with a payload...", pseudo_sock.log_filename, pseudo_sock.log_file_lock)
        except queue.Empty:
            ack_message = utility.create_packet(ack=True, sn=pseudo_sock.get_current_sn(), rn=pseudo_sock.get_current_rn())
            utility.log_message(f"Sending ACK without a payload...", pseudo_sock.log_filename, pseudo_sock.log_file_lock)
        pseudo_sock.send_packet(ack_message)

    @staticmethod
    def handle_timeout(pseudo_sock):
        # Resend SYN, should be the next message in the send queue
        utility.log_message("Resending SYN...", pseudo_sock.log_filename, pseudo_sock.log_file_lock)
        last_sent_packet = pseudo_sock.get_last_sent_packet()
        if last_sent_packet is not None:
            pseudo_sock.send_packet(last_sent_packet)
        else:
            utility.log_message("Nothing to retransmit...", pseudo_sock.log_filename, pseudo_sock.log_file_lock)


class EstablishedStatus(State):
    STATUS_NAME = "ESTABLISHED"

    @staticmethod
    def handle_packet(packet, pseudo_sock):
        is_valid = False
        if utility.are_flags_set(packet, utility.HEADER_FIN):
            is_valid = True
            utility.log_message("Received a FIN! Sending FIN-ACK...", pseudo_sock.log_filename, pseudo_sock.log_file_lock)
            fin_ack_packet = utility.create_packet(fin=True, ack=True)
            pseudo_sock.send_packet(fin_ack_packet)

            utility.log_message("Terminating this socket...", pseudo_sock.log_filename, pseudo_sock.log_file_lock)
            pseudo_sock.terminate_socket(notify_connections_remover=True)
            return

        reply_message = None

        # Parse the packet, determine if its valid and if an ACK should be sent
        # First check if packet contains an ACK
        if utility.are_flags_set(packet, utility.HEADER_ACK) and utility.get_rn(packet) > pseudo_sock.get_current_sn():
            is_valid = True
            if pseudo_sock.last_sent_packet is not None:
                utility.log_message(f"Packet contains an ACK, which means the packet "
                      f"{utility.packet_to_string(pseudo_sock.last_sent_packet)} has been sent successfully!",
                                    pseudo_sock.log_filename, pseudo_sock.log_file_lock)
            pseudo_sock.set_last_sent_packet(None)
            pseudo_sock.set_current_sn(utility.get_rn(packet))

            # Send next packet
            utility.log_message("Adding next packet to reply...", pseudo_sock.log_filename, pseudo_sock.log_file_lock)
            try:
                reply_message = pseudo_sock.send_queue.get(block=False)
                pseudo_sock.send_queue.task_done()
            except queue.Empty:
                utility.log_message("Nothing to transmit...", pseudo_sock.log_filename, pseudo_sock.log_file_lock)
        elif utility.are_flags_set(packet, utility.HEADER_ACK):
            utility.log_message(f"Packet has ACK turned on, but its RN was {utility.get_rn(packet)} and expected was "
                  f"{pseudo_sock.get_current_sn()+1}", pseudo_sock.log_filename, pseudo_sock.log_file_lock)

        # Then, check if packet contains new data
        data_left = packet[0] & utility.HEADER_DATA_LEFT
        if utility.get_sn(packet) == pseudo_sock.get_current_rn() and data_left != 0:
            is_valid = True
            utility.log_message("Packet contains new data!", pseudo_sock.log_filename, pseudo_sock.log_file_lock)

            # Put the payload in the processed messages queue
            # First read the header to determine how many bytes are left
            if data_left == utility.HEADER_DATA_LEFT:
                # Write all the payload
                pseudo_sock.payload_queue.put(packet[utility.HEADER_SIZE:])
            else:
                # Write as many bytes as data_left indicates
                pseudo_sock.payload_queue.put(packet[utility.HEADER_SIZE:utility.HEADER_SIZE+data_left])

                # Write ASCII end of transmission
                pseudo_sock.payload_queue.put(0x4)

            # Increase rn
            pseudo_sock.increase_current_rn()

            # Add an ACK to the reply
            utility.log_message("Adding an ACK to reply...", pseudo_sock.log_filename, pseudo_sock.log_file_lock)
            if reply_message is None:
                reply_message = utility.create_packet(ack=True)
            else:
                reply_message[0] = reply_message[0] | utility.HEADER_ACK

        elif data_left != 0 and utility.get_sn(packet) == pseudo_sock.get_current_rn():
            utility.log_message(f"Packet contained a payload but its sn was {utility.get_sn(packet)} and expected is "
                                f"{pseudo_sock.get_current_rn()}", pseudo_sock.log_filename, pseudo_sock.log_file_lock)

        if reply_message is not None:
            utility.log_message("Sending reply...", pseudo_sock.log_filename, pseudo_sock.log_file_lock)
            pseudo_sock.send_packet(reply_message)
        elif not is_valid:
            utility.log_message("Packet was neither an ACK nor contained new data, ignoring...", pseudo_sock.log_filename,
                                pseudo_sock.log_file_lock)

    @staticmethod
    def handle_timeout(pseudo_sock):
        # Resend the next packet in the send queue
        utility.log_message("Retransmitting latest packet...", pseudo_sock.log_filename, pseudo_sock.log_file_lock)
        last_sent_packet = pseudo_sock.get_last_sent_packet()
        if last_sent_packet is not None:
            # If the latest packet has no payload and there is now one available, add it.
            if last_sent_packet[0] & utility.HEADER_DATA_LEFT == 0:
                try:
                    next_message = pseudo_sock.send_queue.get(block=False)
                    pseudo_sock.send_queue.task_done()
                    next_message[0] = next_message[0] | last_sent_packet[0]
                    last_sent_packet = next_message
                except queue.Empty:
                    pass

            pseudo_sock.send_packet(last_sent_packet)
        else:
            try:
                pseudo_sock.send_packet(pseudo_sock.send_queue.get(block=False))
                pseudo_sock.send_queue.task_done()
            except queue.Empty:
                utility.log_message("Nothing to transmit.", pseudo_sock.log_filename, pseudo_sock.log_file_lock)


class FinSentStatus(State):
    STATUS_NAME = "FIN_SENT"

    @staticmethod
    def handle_packet(packet, pseudo_sock):
        is_valid_fin_ack = utility.are_flags_set(packet, utility.HEADER_ACK, utility.HEADER_FIN) \
                       and utility.get_rn(packet) != pseudo_sock.get_current_sn() \
                       and utility.are_flags_unset(packet, utility.HEADER_SYN)

        if not is_valid_fin_ack:
            utility.log_message("Message received was not a proper FIN-ACK, retrying...", pseudo_sock.log_filename,
                                pseudo_sock.log_file_lock)
            return

        utility.log_message("Message received was a proper FIN-ACK, terminating this socket...", pseudo_sock.log_filename,
                            pseudo_sock.log_file_lock)
        pseudo_sock.terminate_socket(notify_connections_remover=False)

    @staticmethod
    def handle_timeout(pseudo_sock):
        # Resend FIN, should be the next message in the send queue
        utility.log_message("Resending FIN...", pseudo_sock.log_filename, pseudo_sock.log_file_lock)
        last_sent_packet = pseudo_sock.get_last_sent_packet()
        if last_sent_packet is not None:
            pseudo_sock.send_packet(last_sent_packet)
        else:
            utility.log_message("Nothing to retransmit...", pseudo_sock.log_filename, pseudo_sock.log_file_lock)

