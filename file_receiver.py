from node import Node
import file
import time

# Establish the connection
node = Node(('localhost', 65001))
node.set_accepting_connections(True)

time.sleep(5)

remote_node = ("localhost", 65002)
filename = "DesicionesDeDiseño.txt"

filename = file.receive_file(node)
file.send_file(filename, node, remote_node)

#node.close_all()
