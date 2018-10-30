
def send_file(filename, node, destination):
    # Read the file
    with open(filename, "rb") as binary_file:
        # Read the whole file at once
        data = binary_file.read()

    print(len(data))
    print(data)

    # Send the title
    node.send(filename.encode(), destination)

    # Send the contents
    node.send(data, destination)


def receive_file(node):
    # Receive the title
    filename_message = node.recv()
    filename = filename_message.decode("utf-8")
    filename = filename + "_received.txt"  # Avoid name collisions

    # Receive the contents
    message = node.recv()

    # Write the contents
    with open(filename, "wb") as binary_file:
        num_bytes_written = binary_file.write(message)
    return filename