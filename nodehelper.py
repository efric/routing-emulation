import time
from socket import *


def create_listen_socket(self_port):
    sock = socket(AF_INET, SOCK_DGRAM)
    sock.bind(('', self_port))  # socket is reachable by any address machine happens to have
    return sock


def recv_msg(sock, n):
    data, addr = sock.recvfrom(n)
    return data.decode(), addr


def current_milli_time():
    return round(time.time() * 1000)
