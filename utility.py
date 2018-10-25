HEADER_SIZE = 1
PAYLOAD_SIZE = 1
PACKET_SIZE = HEADER_SIZE + PAYLOAD_SIZE
TIMEOUT = 3
HEADER_SYN = 0b0000000010000000
HEADER_ACK = 0b0000000001000000
HEADER_FIN = 0b0000000000100000
HEADER_SN = 0b0000000000010000
HEADER_RN = 0b0000000000001000
HEADER_MESSAGE_END = 0b0000000000000100


def packet_to_string(packet):
    return bin(int.from_bytes(packet, byteorder='little', signed=False))


def are_flags_set(header, *flags):
    for flag in list(flags):
        if (flag & header) == 0:
            return False
    return True


def are_flags_unset(header, *flags):
    for flag in list(flags):
        if (flag & header) != 0:
            return False
    return True


def get_sn(header):
    if (HEADER_SN & header) == 0:
        return False
    return True


def get_rn(header):
    if (HEADER_RN & header) == 0:
        return False
    return True


def create_packet(syn=False, ack=False, fin=False, sn=False, rn=False, data_left=0, payload=bytearray(1)):
    packet = bytearray(PACKET_SIZE)

    # Set flags
    if syn:
        packet[0] = packet[0] | HEADER_SYN
    if ack:
        packet[0] = packet[0] | HEADER_ACK
    if fin:
        packet[0] = packet[0] | HEADER_FIN
    if sn:
        packet[0] = packet[0] | HEADER_SN
    if rn:
        packet[0] = packet[0] | HEADER_RN

    # Add data left and payload
    packet[0] = packet[0] | data_left
    packet[PAYLOAD_SIZE:] = payload
    return packet
