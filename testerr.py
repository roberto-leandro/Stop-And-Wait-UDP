from pseudo_tcp import  PseudoTCPSocket


node = PseudoTCPSocket()
node.bind(("localhost", 65002))
node.accept()
