HEADER_SIZE = 3
PAYLOAD_SIZE = 30
PACKET_SIZE = HEADER_SIZE + PAYLOAD_SIZE
TIMEOUT = 0.05
MAX_TIMEOUTS = 20
HEADER_SYN =       0b00000000000000000000000010000000
HEADER_ACK =       0b00000000000000000000000001000000
HEADER_FIN =       0b00000000000000000000000000100000
HEADER_DATA_LEFT = 0b00000000000000000000000000011111
HEADER_SN =        0b00000000111111110000000000000000
HEADER_RN =        0b00000000000000001111111100000000


def packet_to_string(packet):
    return f"SN={get_sn(packet)}, RN={get_rn(packet)}, SYN={are_flags_set(packet, HEADER_SYN)}, " \
           f"ACK={are_flags_set(packet, HEADER_ACK)}, FIN={are_flags_set(packet, HEADER_FIN)}, " \
           f"data_left={packet[0] & HEADER_DATA_LEFT}, " \
           f"payload={str(packet[HEADER_SIZE:])}"


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
    packet[0] = packet[0] | data_left
    packet[HEADER_SIZE:] = payload

    return packet


def resolve_localhost(address):
    if address[0] == 'localhost':
        address = ('127.0.0.1', address[1])
    return address


def log_message(message, log_filename, lock):
    lock.acquire()
    with open(log_filename, "a+") as log_file:
        log_file.write(message+"\n")
    print(message)
    lock.release()
