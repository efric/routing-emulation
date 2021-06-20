#!/usr/bin/env python3
import sys
from sr_sender import init_sender
from sr_receiver import init_receiver
from sr_helper import is_port_in_use


def init(args):
    if len(args) != 6:
        sys.exit("# ./srnode <self-port> <peer-port> <window-size> [ -d <value-of-n> | -p <value-of-p>]")

    self_port = int(args[1])
    peer_port = int(args[2])
    window_size = int(args[3])
    mode = args[4]
    n = float(args[5])

    if not is_port_in_use(peer_port):
        init_sender(self_port, peer_port, window_size, mode, n)
    else:
        init_receiver(self_port, peer_port, window_size, mode, n)


def main():
    init(sys.argv)


if __name__ == '__main__':
    main()
