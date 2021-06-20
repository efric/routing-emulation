import threading
from sr_helper import recv_msg, create_listen_socket, current_milli_time
from random import seed, random

seed()
start = end = 0
seen = set()
buffer = ['\0'] * 65535
lock = threading.Lock()
count = total = dropped = 0
final = -1
done = False


def find_index():
    for i, v in enumerate(buffer):
        if v == '\0':
            return i


def no_blanks():
    if final == -1:
        return False

    for i in range(final):
        if buffer[i] == '\0':
            return False
    return True


def get_message():
    res = ""
    for ch in buffer:
        if ch == '\0':
            break
        res += ch
    return res


def receive(server, peer_port, window_size, mode, n):
    global start, end, seen, buffer, dropped, count, final, total, done

    while True:
        msg, (ip, port) = recv_msg(server, 65535)
        if port == peer_port:
            lock.acquire()
            if msg[-1] == "\0":
                seq = int(msg[:-2])
                data = msg[-2]
                final = seq
            else:
                seq = int(msg[:-1])
                data = msg[-1]

            if seq > start:
                buffer[seq] = data
                print('[{}] packet{} {} received out of order, buffered'.format(current_milli_time(), seq, data))
            elif seq == start:
                buffer[seq] = data
                start = find_index()
                end = start + window_size - 1
                print('[{}] packet{} {} received'.format(current_milli_time(), seq, data))
            else:
                print('[{}] duplicate packet{} {} received, discarded'.format(current_milli_time(), seq, data))

            packet = str(seq).encode()

            total += 1

            if mode == "-d":
                count = (count + 1) % n
                if count == 0:
                    dropped += 1
                    print('[{}] packet{} {} dropped'.format(current_milli_time(), seq, data))
                else:
                    if seq == final:
                        done = True
                    server.sendto(packet, ('127.0.0.1', peer_port))
                    print('[{}] ACK{} sent, window starts at {}'.format(current_milli_time(), seq, start))
            elif mode == "-p":
                if n <= random():
                    if seq == final:
                        done = True
                    server.sendto(packet, ('127.0.0.1', peer_port))
                    print('[{}] ACK{} sent, window starts at {}'.format(current_milli_time(), seq, start))
                else:
                    dropped += 1
                    print('[{}] packet{} {} dropped'.format(current_milli_time(), seq, data))

            if no_blanks() and done:
                message = get_message()
                print('[{}] Message received: {}'.format(current_milli_time(), message))
                print('[Summary] <{}>/<{}> packets dropped, loss rate = {}%'.format(dropped, total,
                                                                                    round(100 * dropped / total, 2)))
                start = end = dropped = count = total = 0
                final = -1
                seen = set()
                buffer = ['\0'] * 65535
                done = False
            lock.release()


def init_receiver(self_port, peer_port, window_size, mode, n):
    global end
    end = window_size - 1
    receiver = create_listen_socket(self_port)
    threading.Thread(target=receive, args=(receiver, peer_port, window_size, mode, n)).start()
