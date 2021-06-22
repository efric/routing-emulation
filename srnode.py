#!/usr/bin/env python3
import threading
import time
from socket import *
from random import seed, random
import sys

seed()
lock = threading.Lock()
acknowledged = set()
sender_seen = set()
sender_start = sender_end = -1
sender_dropped = sender_total = 0
threads = []

receiver_start = receiver_end = 0
receiver_buffer = ['\0'] * 65535
receiver_count = receiver_total = receiver_dropped = 0
receiver_final = -1
receiver_done = False


# helpers
def create_listen_socket(self_port):
    sock = socket(AF_INET, SOCK_DGRAM)
    sock.bind(('', self_port))  # socket is reachable by any address machine happens to have
    return sock


def recv_msg(sock, n):
    data, addr = sock.recvfrom(n)
    return data.decode(), addr


def current_milli_time():
    return round(time.time() * 1000)


# helpers for receiver side
def find_index():
    for i, v in enumerate(receiver_buffer):
        if v == '\0':
            return i


def no_blanks():
    if receiver_final == -1:
        return False

    for i in range(receiver_final):
        if receiver_buffer[i] == '\0':
            return False
    return True


def get_message():
    res = ""
    for ch in receiver_buffer:
        if ch == '\0':
            break
        res += ch
    return res


def do_listen(server, peer_port, window_size, mode, n):
    global sender_start, sender_end, acknowledged, receiver_buffer, receiver_start, receiver_total, receiver_count, \
        receiver_dropped, receiver_final, receiver_done
    receiver_end = window_size - 1
    first_receive = True

    while True:
        data, (ip, port) = recv_msg(server, 65535)
        lock.acquire()
        if port == peer_port:
            if data.isdigit():
                ack = int(data)
                acknowledged.add(ack)

                if ack == sender_start:
                    difference = sender_seen.difference(acknowledged)
                    sender_start = min(difference) if difference else max(acknowledged) + 1
                    sender_end = sender_start + window_size - 1
                print('[{}] ACK{} received, window starts at {}'.format(current_milli_time(), ack, sender_start))
            else:
                if first_receive:
                    print("")
                    first_receive = False

                if data[-1] == "\0":
                    seq = int(data[:-2])
                    data = data[-2]
                    receiver_final = seq
                else:
                    seq = int(data[:-1])
                    data = data[-1]

                if seq > receiver_start:
                    receiver_buffer[seq] = data
                    print('[{}] packet{} {} received out of order, buffered'.format(current_milli_time(), seq, data))
                elif seq == receiver_start:
                    receiver_buffer[seq] = data
                    receiver_start = find_index()
                    receiver_end = receiver_start + window_size - 1
                    print('[{}] packet{} {} received'.format(current_milli_time(), seq, data))
                else:
                    print('[{}] duplicate packet{} {} received, discarded'.format(current_milli_time(), seq, data))

                packet = str(seq).encode()

                receiver_total += 1

                if mode == "-d":
                    receiver_count = (receiver_count + 1) % n
                    if receiver_count == 0:
                        receiver_dropped += 1
                        print('[{}] packet{} {} dropped'.format(current_milli_time(), seq, data))
                    else:
                        if seq == receiver_final:
                            receiver_done = True
                        server.sendto(packet, ('127.0.0.1', peer_port))
                        print('[{}] ACK{} sent, window starts at {}'.format(current_milli_time(), seq, receiver_start))
                elif mode == "-p":
                    if n <= random():
                        if seq == receiver_final:
                            receiver_done = True
                        server.sendto(packet, ('127.0.0.1', peer_port))
                        print('[{}] ACK{} sent, window starts at {}'.format(current_milli_time(), seq, receiver_start))
                    else:
                        receiver_dropped += 1
                        print('[{}] packet{} {} dropped'.format(current_milli_time(), seq, data))

                if no_blanks() and receiver_done:
                    message = get_message()
                    print('[{}] Message received: {}'.format(current_milli_time(), message))
                    print(
                        '[Summary] <{}>/<{}> packets dropped, loss rate = {}%'.format(receiver_dropped, receiver_total,
                                                                                      round(
                                                                                          100 * receiver_dropped / receiver_total,
                                                                                          2)))
                    receiver_start = receiver_end = receiver_dropped = receiver_count = receiver_total = 0
                    receiver_final = -1
                    receiver_buffer = ['\0'] * 65535
                    receiver_done = False
                    print('node> ', end="", flush=True)
                    first_receive = True
        lock.release()


def timeout(server, seq, packet, peer_port, sender_buffer):
    global acknowledged, sender_dropped, sender_total

    while True:
        time.sleep(0.5)
        lock.acquire()
        if seq in acknowledged:
            if len(acknowledged) == len(sender_buffer):
                for t in threads:
                    if threading.current_thread() != t:
                        t.join()
                print('[Summary] <{}>/<{}> packets dropped, loss rate = {}%'.format(sender_dropped, sender_total,
                                                                                    round(
                                                                                        100 * sender_dropped / sender_total,
                                                                                        2)))
                acknowledged.clear()
                sender_seen.clear()
                threads.clear()
                sender_dropped = sender_total = 0
            lock.release()
            break
        print('[{}] packet{} timeout, resending'.format(current_milli_time(), seq))
        server.sendto(packet, ('127.0.0.1', peer_port))
        sender_seen.add(seq)
        lock.release()


def send(server, peer_port, window_size, buffer, mode, drop):
    global sender_seen, sender_start, sender_end, acknowledged

    def send_msg(seq, data, done, mode, count, drop, sender_buffer):
        global sender_dropped, sender_total

        lock.acquire()
        packet = str(seq) + data
        if done:
            packet += "\0"
        packet = packet.encode()

        if mode == "-d":
            if count == 0:
                sender_dropped += 1
                print('[{}] packet{} dropped'.format(current_milli_time(), seq))
            else:
                server.sendto(packet, ('127.0.0.1', peer_port))
                print('[{}] packet{} {} sent'.format(current_milli_time(), seq, data))
        elif mode == "-p":
            if drop <= random():
                server.sendto(packet, ('127.0.0.1', peer_port))
                print('[{}] packet{} {} sent'.format(current_milli_time(), seq, data))
            else:
                sender_dropped += 1
                print('[{}] packet{} dropped'.format(current_milli_time(), seq))
        sender_seen.add(seq)
        sender_total += 1
        lock.release()
        threads.append(threading.Thread(target=timeout, args=(server, seq, packet, peer_port, sender_buffer)))
        threads[-1].start()

    lock.acquire()
    sender_start = count = 0
    sender_end = window_size - 1
    lock.release()

    while True:
        lock.acquire()
        sender_end = min(sender_end, len(buffer))
        if sender_start >= len(buffer):
            lock.release()
            break
        curr_sender_start, curr_sender_end = sender_start, sender_end
        lock.release()

        for n in range(curr_sender_start, curr_sender_end):
            lock.acquire()
            viable = n not in sender_seen
            lock.release()
            if viable:
                if mode == "-d":
                    count = (count + 1) % drop
                if n == len(buffer) - 1:
                    send_msg(n, buffer[n], True, mode, count, drop, buffer)
                else:
                    send_msg(n, buffer[n], False, mode, count, drop, buffer)


def do_send(server, peer_port, window_size, mode, n):
    global threads
    while True:
        user = input("node> ")
        user_input = user.split(" ")

        if user_input[0] == "send":
            msg = ' '.join(user_input[1:])
            send(server, peer_port, window_size, msg, mode, n)

        for t in threads:
            if t:
                t.join()


def init_srp(self_port, peer_port, window_size, mode, n):
    server = create_listen_socket(self_port)
    threading.Thread(target=do_listen, args=(server, peer_port, window_size, mode, n)).start()
    threading.Thread(target=do_send, args=(server, peer_port, window_size, mode, n)).start()


def init(args):
    if len(args) != 6:
        sys.exit("./srnode <self-port> <peer-port> <window-size> [ -d <value-of-n> | -p <value-of-p>]")

    self_port = int(args[1])
    peer_port = int(args[2])
    window_size = int(args[3])
    mode = args[4]
    n = float(args[5])

    if mode == "-p" and (n < 0 or n > 1):
        sys.exit("probability must be between 0 and 1")

    if mode == "-d" and n < 0:
        sys.exit("dropped number must not be negative")

    init_srp(self_port, peer_port, window_size, mode, n)


def main():
    init(sys.argv)


if __name__ == '__main__':
    main()
