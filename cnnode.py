#!/usr/bin/env python3
import sys
import threading
import json
from random import seed, random
from copy import deepcopy
from nodehelper import *

seed()

# constants
window_size = 5
probe_msg = "abcdefghij"

# dv
lock = threading.Lock()
rt = {}
next_hop = {}
neighbors = set()

# sr
change = False
senders = {}
receivers = {}
start_probe = False


def print_rt(me):
    print('[{}] Node {} Routing Table'.format(current_milli_time(), me))
    for node, distance in rt.items():
        if node == me or node == -1:
            continue

        if node in next_hop:
            print('- ({:.2f}) -> Node {}; Next hop -> Node {}'.format(distance, node, next_hop[node]))
        else:
            print('- ({:.2f}) -> Node {}'.format(distance, node))


def timeout(server, seq, packet, peer_port, done):
    global change
    while True:
        time.sleep(0.5)
        lock.acquire()
        if seq in senders[peer_port]["acknowledged"]:
            if done:
                new_rate = senders[peer_port]["dropped"] / senders[peer_port]["total"]
                if new_rate != rt[peer_port]:
                    change = True
                rt[peer_port] = new_rate
            lock.release()
            break
        server.sendto(packet, ('127.0.0.1', peer_port))
        senders[peer_port]["seen"].add(seq)
        lock.release()


def send_probe(server, node, drop):
    threads = []

    def send_msg(seq, data, done, drop, node):
        lock.acquire()
        packet = str(seq) + data
        if done:
            packet += "\0"
        packet = packet.encode()

        if drop <= random():
            server.sendto(packet, ('127.0.0.1', node))
        else:
            senders[node]["dropped"] += 1
        senders[node]["seen"].add(seq)
        senders[node]["total"] += 1
        lock.release()
        if drop <= random():
            server.sendto(packet, ('127.0.0.1', node))
        threads.append(threading.Thread(target=timeout, args=(server, seq, packet, node, done)))
        threads[-1].start()

    while True:
        lock.acquire()
        senders[node]["end"] = min(senders[node]["end"], len(probe_msg))
        if senders[node]["start"] >= len(probe_msg):
            lock.release()
            break
        curr_sender_start, curr_sender_end = senders[node]["start"], senders[node]["end"]
        lock.release()

        for n in range(curr_sender_start, curr_sender_end):
            lock.acquire()
            viable = n not in senders[node]["seen"]
            lock.release()
            if viable:
                if n == len(probe_msg) - 1:
                    send_msg(n, probe_msg[n], True, drop, node)
                else:
                    send_msg(n, probe_msg[n], False, drop, node)

    for t in threads:
        if t:
            t.join()


def probe(server):
    while True:
        lock.acquire()
        if not start_probe:
            lock.release()
            continue
        lock.release()
        for node in senders.keys():
            if node == -1 or senders[node]["loss"] == -1:  # haven't received rate yet
                continue
            drop = senders[node]["loss"]
            threading.Thread(target=send_probe, args=(server, node, drop)).start()
        time.sleep(3)


def update_timer(server, ip, me):
    global change
    while True:
        lock.acquire()
        if change:
            sendchanges(server, ip, me)
            change = False
        lock.release()
        time.sleep(5)


def sendchanges(server, ip, me):
    for neighbor in neighbors:
        curr_table = deepcopy(rt)
        if neighbor in receivers:
            curr_table[-1] = receivers[neighbor]["loss"]
        print('[{}] Message sent from Node {} to Node {}'.format(current_milli_time(), me, neighbor))
        server.sendto(str.encode(json.dumps(curr_table)), (ip, neighbor))


def find_index(receiver_buffer):
    for i, v in enumerate(receiver_buffer):
        if v == '\0':
            return i


def no_blanks(receiver_final, receiver_buffer):
    if receiver_final == -1:
        return False

    for i in range(receiver_final):
        if receiver_buffer[i] == '\0':
            return False
    return True


def update_rt(data, port, first, server, ip, me):
    global start_probe

    lock.acquire()
    table_change = False
    if data.isdigit():  # SENDER received an ack
        ack = int(data)
        senders[port]["acknowledged"].add(ack)

        if ack == senders[port]["start"]:
            seen = senders[port]["seen"]
            acknowledged = senders[port]["acknowledged"]

            difference = seen.difference(acknowledged)
            sender_start = min(difference) if difference else max(acknowledged) + 1
            sender_end = sender_start + window_size - 1

            senders[port]["start"] = sender_start
            senders[port]["end"] = sender_end
    elif data[0].isdigit():  # RECEIVER received data

        if data[-1] == "\0":
            seq = int(data[:-2])
            data = data[-2]
            receivers[port]["receiver_final"] = seq
        else:
            seq = int(data[:-1])
            data = data[-1]

        if seq > receivers[port]["start"]:
            receivers[port]["buffer"][seq] = data
        elif seq == receivers[port]["start"]:
            receivers[port]["buffer"][seq] = data
            receivers[port]["start"] = find_index(receivers[port]["buffer"])

        packet = str(seq).encode()
        server.sendto(packet, ('127.0.0.1', port))

        if no_blanks(receivers[port]["receiver_final"], receivers[port]["buffer"]) and receivers[port]["done"]:
            receivers[port]["start"] = receivers[port]["end"] = 0
            receivers[port]["buffer"] = ['\0'] * 65535
            receivers[port]["done"] = False
            receivers[port]["receiver_final"] = -1
    else:  # DV NODE
        print('[{}] Message received from Node {} to Node {}'.format(current_milli_time(), port, me))
        d = json.loads(data)
        start_probe = True

        for node, dv in d.items():
            node, dv = int(node), float(dv)
            if node == -1:  # received probe rate
                senders[port]["loss"] = dv
            else:
                if node not in rt or rt[node] == 0 or rt[port] + dv < rt[node]:
                    table_change = True
                    rt[node] = rt[port] + dv
                    next_hop[node] = port

        if table_change or first:
            sendchanges(server, ip, me)

        print_rt(me)
    lock.release()


def listen(server, me):
    first = True
    while True:
        neighbor_table, (ip, port) = recv_msg(server, 65535)
        threading.Thread(target=update_rt, args=(neighbor_table, port, first, server, ip, me)).start()
        if first:
            first = False


def status():
    while True:
        lock.acquire()
        for node in senders.keys():
            rate = 0 if senders[node]["total"] == 0 else senders[node]["dropped"] / senders[node]["total"]
            print('[{}] Link to {}: {} packets sent, {} packets lost, loss rate {}'.format(
                current_milli_time(), node, senders[node]["total"], senders[node]["dropped"],
                rate))
        lock.release()
        time.sleep(1)


def init(args):
    global start_probe

    local_port = int(args[1])
    if local_port < 1024 or local_port > 65534:
        exit("UDP port number must be between 1024-65534")

    if args[-1] == "last":
        neighbor_info = args[2:-1]
        last = True
    else:
        neighbor_info = args[2:]
        last = False

    receiving_list = neighbor_info[neighbor_info.index("receive") + 1:neighbor_info.index("send")]
    sending_list = [int(n) for n in neighbor_info[neighbor_info.index("send") + 1:]]

    for neighbor_port in sending_list:
        if neighbor_port < 1024 or neighbor_port > 65534:
            exit("UDP port number must be between 1024-65534")
        rt[neighbor_port] = 0
        neighbors.add(neighbor_port)
        senders[neighbor_port] = {}
        senders[neighbor_port]["start"] = 0
        senders[neighbor_port]["end"] = window_size - 1
        senders[neighbor_port]["dropped"] = 0
        senders[neighbor_port]["total"] = 0
        senders[neighbor_port]["seen"] = set()
        senders[neighbor_port]["acknowledged"] = set()
        senders[neighbor_port]["loss"] = -1

    for i in range(0, len(receiving_list), 2):
        neighbor_port, initial_loss_rate = int(receiving_list[i]), float(
            receiving_list[i + 1])  # i+1 is rate for sr protocol
        if neighbor_port < 1024 or neighbor_port > 65534:
            exit("UDP port number must be between 1024-65534")
        rt[neighbor_port] = 0
        neighbors.add(neighbor_port)
        receivers[neighbor_port] = {}
        receivers[neighbor_port]["loss"] = initial_loss_rate
        receivers[neighbor_port]["buffer"] = ['\0'] * 65535
        receivers[neighbor_port]["start"] = 0
        receivers[neighbor_port]["end"] = window_size - 1
        receivers[neighbor_port]["done"] = False
        receivers[neighbor_port]["receiver_final"] = -1

    rt[local_port] = 0
    server = create_listen_socket(local_port)

    print_rt(local_port)
    if last:
        start_probe = True
        sendchanges(server, '127.0.0.1', local_port)

    threading.Thread(target=probe, args=(server,)).start()
    threading.Thread(target=update_timer, args=(server, '127.0.0.1', local_port)).start()
    threading.Thread(target=status).start()
    listen(server, local_port)


def main():
    init(sys.argv)


if __name__ == '__main__':
    main()
