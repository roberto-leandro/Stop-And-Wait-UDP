from pseudo_tcp import PseudoTCPSocket

# Establish the connection
node = PseudoTCPSocket()
node.bind(("localhost", 65002))
node.connect(("localhost", 65001))

FILENAME = "DesicionesDeDiseño.txt"

# Read and send the file
with open(FILENAME, "rb") as binary_file:
    # Read the whole file at once
    data = binary_file.read()
    print(len(data))
    print(data)

    node.send(FILENAME.encode())

    node.send(data)
