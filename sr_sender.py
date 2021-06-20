import threading
import time
from socket import *
from random import seed, random
from sr_helper import recv_msg, create_listen_socket, current_milli_time

seed()
lock = threading.Lock()
acknowledged = set()
seen = set()
start = -1
end = -1
dropped = 0
total = 0
threads = []


def do_listen(server, peer_port, window_size):
    global start, end, acknowledged

    while True:
        data, (ip, port) = recv_msg(server, 65535)
        lock.acquire()
        if port == peer_port:
            ack = int(data)
            acknowledged.add(ack)

            if ack == start:
                difference = seen.difference(acknowledged)
                start = min(difference) if difference else max(acknowledged) + 1
                end = start + window_size - 1
            print('[{}] ACK{} received, window starts at {}'.format(current_milli_time(), ack, start))
        lock.release()


def timeout(server, seq, packet, peer_port, done):
    global acknowledged, dropped, total

    while True:
        time.sleep(0.5)
        lock.acquire()
        if seq in acknowledged:
            if done:
                print('[Summary] <{}>/<{}> packets dropped, loss rate = {}%'.format(dropped, total,
                                                                                    round(100 * dropped / total, 2)))
                acknowledged.clear()
                seen.clear()
                threads.clear()
                dropped = total = 0
            lock.release()
            break
        print('[{}] packet{} timeout, resending'.format(current_milli_time(), seq))
        server.sendto(packet, ('127.0.0.1', peer_port))
        seen.add(seq)
        lock.release()


def send(server, peer_port, window_size, buffer, mode, drop):
    global seen, start, end, acknowledged

    def send_msg(seq, data, done, mode, count, drop):
        global dropped, total

        lock.acquire()
        packet = str(seq) + data
        if done:
            packet += "\0"
        packet = packet.encode()

        if mode == "-d":
            if count == 0:
                dropped += 1
                print('[{}] packet{} dropped'.format(current_milli_time(), seq))
            else:
                server.sendto(packet, ('127.0.0.1', peer_port))
                print('[{}] packet{} {} sent'.format(current_milli_time(), seq, data))
        elif mode == "-p":
            if drop <= random():
                server.sendto(packet, ('127.0.0.1', peer_port))
                print('[{}] packet{} {} sent'.format(current_milli_time(), seq, data))
            else:
                dropped += 1
                print('[{}] packet{} dropped'.format(current_milli_time(), seq))
        seen.add(seq)
        total += 1
        lock.release()
        threads.append(threading.Thread(target=timeout, args=(server, seq, packet, peer_port, done)))
        threads[-1].start()

    lock.acquire()
    start = count = 0
    end = window_size - 1
    lock.release()

    while True:
        lock.acquire()
        end = min(end, len(buffer))
        if start >= len(buffer):
            lock.release()
            break
        curr_start, curr_end = start, end
        lock.release()

        for n in range(curr_start, curr_end):
            lock.acquire()
            viable = n not in seen
            lock.release()
            if viable:
                if mode == "-d":
                    count = (count + 1) % drop
                if n == len(buffer) - 1:
                    send_msg(n, buffer[n], True, mode, count, drop)
                else:
                    send_msg(n, buffer[n], False, mode, count, drop)


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


def init_sender(self_port, peer_port, window_size, mode, n):
    server = create_listen_socket(self_port)
    threading.Thread(target=do_listen, args=(server, peer_port, window_size)).start()
    threading.Thread(target=do_send, args=(server, peer_port, window_size, mode, n)).start()
