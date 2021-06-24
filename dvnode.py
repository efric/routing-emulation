#!/usr/bin/env python3
import sys
import threading
import json
from nodehelper import *

lock = threading.Lock()
rt = {}
next_hop = {}
neighbors_cost = {}


def print_rt(me):
    print('[{}] Node {} Routing Table'.format(current_milli_time(), me))
    for node, distance in rt.items():
        if node == me:
            continue

        if node in next_hop:
            print('- ({:.2f}) -> Node {}; Next hop -> Node {}'.format(distance, node, next_hop[node]))
        else:
            print('- ({:.2f}) -> Node {}'.format(distance, node))


def sendchanges(server, ip, me):
    mytable = json.dumps(rt)
    for neighbor in neighbors_cost.keys():
        print('[{}] Message sent from Node {} to Node {}'.format(current_milli_time(), me, neighbor))
        server.sendto(str.encode(mytable), (ip, neighbor))


def listen(server, me):
    first = True
    while True:
        lock.acquire()
        change = False
        neighbor_table, (ip, port) = recv_msg(server, 65535)
        print('[{}] Message received from Node {} to Node {}'.format(current_milli_time(), port, me))
        d = json.loads(neighbor_table)

        for node, dv in d.items():
            node, dv = int(node), round(float(dv), 2)
            if node not in rt or neighbors_cost[port] + dv < rt[node]:
                change = True
                rt[node] = neighbors_cost[port] + dv
                next_hop[node] = port

        if change or first:
            sendchanges(server, ip, me)
            first = False

        print_rt(me)
        lock.release()


def init(args):
    if len(args) < 4:
        sys.exit("./dvnode.py <local-port> <neighbor1-port> <loss-rate-1> <neighbor2-port> <loss-rate-2> ... [last]")
    local_port = int(args[1])
    if local_port < 1024 or local_port > 65534:
        exit("UDP port number must be between 1024-65534")

    if args[-1] == "last":
        neighbor_info = args[2:-1]
        last = True
    else:
        neighbor_info = args[2:]
        last = False

    for i in range(0, len(neighbor_info), 2):
        neighbor_port, loss_rate = int(neighbor_info[i]), float(neighbor_info[i + 1])
        if neighbor_port < 1024 or neighbor_port > 65534:
            exit("UDP port number must be between 1024-65534")
        rt[neighbor_port] = loss_rate
        neighbors_cost[neighbor_port] = loss_rate

    rt[local_port] = 0
    server = create_listen_socket(local_port)

    print_rt(local_port)
    if last:
        sendchanges(server, '127.0.0.1', local_port)
    listen(server, local_port)


def main():
    init(sys.argv)


if __name__ == '__main__':
    main()
