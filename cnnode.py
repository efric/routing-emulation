#!/usr/bin/env python3
import sys
import threading
import json
from random import seed, random
from copy import deepcopy
from nodehelper import *
from collections import defaultdict

seed()

# constants
window_size = 5
probe_msg = "Far far away, behind the word mountains, far from."

# dv
lock = threading.Lock()
rt = {}
next_hop = {}
neighbors = set()

# sr
change = False
sender = {}
receiver = {}
start_probe = False
neighbors_cost = {}


# helpers for SR
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


def print_rt(me):
    print('[{}] Node {} Routing Table'.format(current_milli_time(), me))
    for node, distance in rt.items():
        if node == me or node == -1:
            continue

        if node in next_hop:
            print('- ({:.2f}) -> Node {}; Next hop -> Node {}'.format(distance, node, next_hop[node]))
        else:
            print('- ({:.2f}) -> Node {}'.format(distance, node))


def timeout(server, seq, packet, peer_port):
    global change
    while True:
        time.sleep(0.5)
        lock.acquire()
        if seq in sender[peer_port]["acknowledged"]:
            lock.release()
            break
        server.sendto(packet, ('127.0.0.1', peer_port))
        sender[peer_port]["seen"].add(seq)
        lock.release()


def send_probe(server, node, drop, threads):
    def send_msg(seq, data, done, drop, node):
        lock.acquire()
        packet = str(seq) + data
        if done:
            packet += "\0"
        packet = packet.encode()

        if drop <= random():
            server.sendto(packet, ('127.0.0.1', node))
        else:
            sender[node]["dropped"] += 1
        sender[node]["seen"].add(seq)
        sender[node]["total"] += 1
        lock.release()
        if drop <= random():
            server.sendto(packet, ('127.0.0.1', node))
        threads.append(threading.Thread(target=timeout, args=(server, seq, packet, node)))
        threads[-1].start()

    lock.acquire()
    sender[node]["start"] = 0
    sender[node]["end"] = window_size - 1
    lock.release()

    while True:
        lock.acquire()
        sender[node]["end"] = min(sender[node]["end"], len(probe_msg))
        if sender[node]["start"] >= len(probe_msg):
            lock.release()
            break
        curr_sender_start, curr_sender_end = sender[node]["start"], sender[node]["end"]
        lock.release()

        for n in range(curr_sender_start, curr_sender_end):
            lock.acquire()
            viable = n not in sender[node]["seen"]
            lock.release()
            if viable:
                if n == len(probe_msg) - 1:
                    send_msg(n, probe_msg[n], True, drop, node)
                else:
                    send_msg(n, probe_msg[n], False, drop, node)


def send_probe_wrapper(server, node, drop):
    global change

    threads = []
    send_probe(server, node, drop, threads)

    for t in threads:
        if t:
            t.join()
    lock.acquire()
    sender[node]["acknowledged"].clear()
    sender[node]["seen"].clear()
    new_rate = round(sender[node]["dropped"] / sender[node]["total"], 2)
    if node not in neighbors_cost or new_rate != neighbors_cost[node]:
        print(new_rate, node, rt, neighbors_cost)
        change = True
        neighbors_cost[node] = new_rate
        rt[node] = new_rate
    lock.release()


def probe(server):  # send probe message every 3 seconds to probe receivers
    global start_probe

    while True:
        for node in sender.keys():
            if sender[node]["loss"] != -1:  # if we have received loss rate from a receiver then start probe message
                lock.acquire()
                start_probe = True
                sender[node]["dropped"] = 0
                sender[node]["total"] = 0
                drop = sender[node]["loss"]
                lock.release()
                threading.Thread(target=send_probe_wrapper, args=(server, node, drop)).start()
        time.sleep(10)  # send probe packet in 20 second intervals


def update_timer(server, ip, me):
    global change
    while True:
        if start_probe:
            lock.acquire()
            if change:
                sendchanges(server, ip, me)
                change = False
            lock.release()
            time.sleep(5)


def sendchanges(server, ip, me):
    for neighbor in neighbors:
        curr_table = deepcopy(rt)
        if neighbor in receiver:
            curr_table[-1] = receiver[neighbor]["loss"]
        print("send", neighbor, curr_table)
        print('[{}] Message sent from Node {} to Node {}'.format(current_milli_time(), me, neighbor))
        server.sendto(str.encode(json.dumps(curr_table)), (ip, neighbor))


def update_rt(data, port, first, server, ip, me):
    lock.acquire()
    table_change = False
    if data.isdigit():  # SENDER received an ack
        ack = int(data)
        sender[port]["acknowledged"].add(ack)

        if ack == sender[port]["start"]:
            seen = sender[port]["seen"]
            acknowledged = sender[port]["acknowledged"]

            difference = seen.difference(acknowledged)
            sender_start = min(difference) if difference else max(acknowledged) + 1
            sender_end = sender_start + window_size - 1

            sender[port]["start"] = sender_start
            sender[port]["end"] = sender_end
    elif data[0].isdigit():  # RECEIVER received data

        if data[-1] == "\0":
            seq = int(data[:-2])
            data = data[-2]
            receiver[port]["receiver_final"] = seq
        else:
            seq = int(data[:-1])
            data = data[-1]

        if seq > receiver[port]["start"]:
            receiver[port]["buffer"][seq] = data
        elif seq == receiver[port]["start"]:
            receiver[port]["buffer"][seq] = data
            receiver[port]["start"] = find_index(receiver[port]["buffer"])

        packet = str(seq).encode()
        server.sendto(packet, ('127.0.0.1', port))

        if no_blanks(receiver[port]["receiver_final"], receiver[port]["buffer"]):
            receiver[port]["start"] = receiver[port]["end"] = 0
            receiver[port]["buffer"] = ['\0'] * 65535
            receiver[port]["receiver_final"] = -1
    else:  # DV NODE
        print('[{}] Message received from Node {} to Node {}'.format(current_milli_time(), port, me))
        d = {int(node): round(float(dv), 2) for node, dv in json.loads(data).items()}

        print(port, d)

        if -1 in d:  # received probe rate
            sender[port]["loss"] = d[-1]

        if port in receiver and d[me] != 0:  # received link cost from sender
            table_change = True
            neighbors_cost[port] = d[me]
            rt[port] = d[me]

        if port in neighbors_cost:
            for node, dv in d.items():
                if node == -1:
                    continue
                else:
                    if dv != 0 and neighbors_cost[port] != 0 and (node not in rt or neighbors_cost[port] + dv < rt[node]):
                        table_change = True
                        rt[node] = neighbors_cost[port] + dv
                        next_hop[node] = port

        if table_change or first:
            sendchanges(server, ip, me)

        print_rt(me)
    lock.release()


def status():
    if start_probe:
        while True:
            lock.acquire()
            for node in sender.keys():
                rate = 0 if sender[node]["total"] == 0 else sender[node]["dropped"] / sender[node]["total"]
                print('[{}] Link to {}: {} packets sent, {} packets lost, loss rate {}'.format(
                    current_milli_time(), node, sender[node]["total"], sender[node]["dropped"],
                    rate))
            lock.release()
            time.sleep(1)


def listen(server, me):
    first = True
    while True:
        neighbor_table, (ip, port) = recv_msg(server, 65535)
        threading.Thread(target=update_rt, args=(neighbor_table, port, first, server, ip, me)).start()
        if first:
            first = False


def init(args):
    if len(args) < 4:
        sys.exit(
            "cnnode <local-port> receive <neighbor1-port>"
            "<loss-rate-1> <neighbor2-port> <loss-rate-2> ... "
            "<neighborM-port> <loss-rate-M> send <neighbor(M+1)-port>"
            "<neighbor(M+2)-port> ... <neighborN-port> [last]")
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

    for port in sending_list:
        if port < 1024 or port > 65534:
            exit("UDP port number must be between 1024-65534")
        rt[port] = 0
        neighbors.add(port)
        sender[port] = {}
        sender[port]["dropped"] = 0
        sender[port]["total"] = 0
        sender[port]["seen"] = set()
        sender[port]["acknowledged"] = set()
        sender[port]["loss"] = -1

    for i in range(0, len(receiving_list), 2):
        port, initial_loss_rate = int(receiving_list[i]), float(
            receiving_list[i + 1])
        if port < 1024 or port > 65534:
            exit("UDP port number must be between 1024-65534")
        rt[port] = 0
        neighbors.add(port)
        receiver[port] = {}
        receiver[port]["loss"] = initial_loss_rate
        receiver[port]["buffer"] = ['\0'] * 65535
        receiver[port]["start"] = 0
        receiver[port]["end"] = window_size - 1
        receiver[port]["done"] = False
        receiver[port]["receiver_final"] = -1

    rt[local_port] = 0
    server = create_listen_socket(local_port)

    print_rt(local_port)
    if last:
        sendchanges(server, '127.0.0.1', local_port)

    threading.Thread(target=probe, args=(server,)).start()
    threading.Thread(target=update_timer, args=(server, '127.0.0.1', local_port)).start()
    threading.Thread(target=status).start()
    listen(server, local_port)


def main():
    init(sys.argv)


if __name__ == '__main__':
    main()
