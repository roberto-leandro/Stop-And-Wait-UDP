from node import Node
import file
import time

# Establish the connection
node = Node(('localhost', 65001))
node.set_accepting_connections(True)

remote_node = ("localhost", 65002)
filename = "first_message.txt"

file.receive_file(node)
file.send_file(filename, node, remote_node)
