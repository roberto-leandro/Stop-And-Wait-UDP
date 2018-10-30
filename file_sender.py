from node import Node
import file

# Establish the connection
node = Node(("localhost", 65002))
remote_node = ("localhost", 65001)
node.connect(remote_node)

filename = "segundo_mensaje.txt"

file.send_file(filename, node, remote_node)
file.receive_file(node)
