import socket


sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

sock.sendto(b'testData' * 15, ('127.0.0.1', 123))
data, addr = sock.recvfrom(1024)
print(data, addr)
