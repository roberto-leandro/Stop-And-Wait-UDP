from pseudo_tcp import  PseudoTCPSocket

# Establish the connection
node = PseudoTCPSocket()
node.bind(('localhost', 65001))
node.accept()


message = node.recv()
with open("test_copy.txt", "wb") as binary_file:
    num_bytes_written = binary_file.write(message)
