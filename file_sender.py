from node import Node

# Establish the connection
node = Node(("localhost", 65002))
receiver = ("localhost", 65001)
node.connect(receiver)

FILENAME = "DesicionesDeDiseño.txt"

# Read the file
with open(FILENAME, "rb") as binary_file:
    # Read the whole file at once
    data = binary_file.read()

print(len(data))
print(data)

# Send the title
node.send(FILENAME.encode(), receiver)

# Send the contents
node.send(data, receiver)
#node.close(receiver)
