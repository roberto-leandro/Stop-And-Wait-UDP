from pseudo_tcp import PseudoTCPSocket

# Establish the connection
node = PseudoTCPSocket()
node.bind(('localhost', 65001))
node.accept()


filename_message = node.recv()
filename = filename_message.decode("utf-8")
filename = filename + "_received.txt"  # Avoid name collisions
message = node.recv()
with open(filename, "wb") as binary_file:
    num_bytes_written = binary_file.write(message)
    node.close()
