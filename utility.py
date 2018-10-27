HEADER_SIZE = 3
PAYLOAD_SIZE = 1
PACKET_SIZE = HEADER_SIZE + PAYLOAD_SIZE
TIMEOUT = 0.5
HEADER_SYN = 0b00000000000000000000000010000000
HEADER_ACK = 0b00000000000000000000000001000000
HEADER_FIN = 0b00000000000000000000000000100000
HEADER_SN =  0b00000000111111110000000000000000
HEADER_RN =  0b00000000000000001111111100000000
HEADER_MESSAGE_END = 0b00000000000000000001000000000000


def packet_to_string(packet):
    return bin(int.from_bytes(packet, byteorder='little', signed=False))


def are_flags_set(packet, *flags):
    header = packet[0]
    for flag in list(flags):
        if (flag & header) == 0:
            return False
    return True


def are_flags_unset(packet, *flags):
    header = packet[0]
    for flag in list(flags):
        if (flag & header) != 0:
            return False
    return True


def get_sn(packet):
    return packet[2]


def get_rn(packet):
    return packet[1]


def create_packet(syn=False, ack=False, fin=False, sn=0, rn=0, data_left=0, payload=bytearray(1)):
    packet = bytearray(PACKET_SIZE)

    # Set flags
    if syn:
        packet[0] = packet[0] | HEADER_SYN
    if ack:
        packet[0] = packet[0] | HEADER_ACK
    if fin:
        packet[0] = packet[0] | HEADER_FIN

    packet[1] = rn
    packet[2] = sn

    # Add data left and payload
    # packet[0] = packet[0] | data_left
    packet[HEADER_SIZE:] = payload

    return packet
