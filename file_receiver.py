from node import Node


# Establish the connection
node = Node(('localhost', 65001))
node.set_accepting_connections(True)

sender = ("localhost", 65002)

# Receive the title
filename_message = node.recv(sender)
filename = filename_message.decode("utf-8")
filename = filename + "_received.txt"  # Avoid name collisions

# Receive the contents
message = node.recv(sender)

# Write the contents
with open(filename, "wb") as binary_file:
    num_bytes_written = binary_file.write(message)
    #node.close_all()
