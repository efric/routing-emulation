Eric Feng,
ef2648

Part 2: Selective Repeat protocol


Usage:
To start the SR protocol, please use the same command as provided in the programming assignment instructions. In other words,

$ ./srnode <self-port> <peer-port> <window-size> [ -d <value-of-n> | -p <value-of-p>]

where d represents drop packets deterministically and p represents drop packets probabilistically. p must be a number between 0-1 (where 0 means never drop, 1 means always drop) and d must be a nonnegative number. 

Implementation details:
The program begins with the function 'init' which is used to filter our improper user input and exit early. Following that, we enter 'init_srp' which is where the program actually begins. We initialize two threads. One calls 'do_listen', which is the main thread responsible for listening to responses (ACK, etc) and the other, 'do_send' for sending the message. 

do_send performs sliding window technique across the message; the start/end of the window is increased whenever it receives an appropriate ACK from the receiver according to SR protocol. Each letter is sent in a separate message and is prepended by the sequence number. It is then dropped or sent according to -d/-p value then enters a timeout thread. The timeout thread sleeps for 0.5 seconds and wakes up to check if the sequence number has been acknowledged by listen thread. If not, it will try to resend the message. On the last character, we append the packet by the null terminator \0 to let the receiver side know we are done.

do_listen is responsible both for parsing ACKs on sender side and receiver side operations. On ACK, we add the sequence number to an acknowledged set and update the window. On receiver side, we extract the character and sequence number and send ACK back to sender side according to -d/-p.

This program is bidirectional and thus may send messages from either side of the peer port. Messages must be sent after the previous message has arrived to not mess up window. 

Edge case: If a receiver finishes but sender still hasn't received ack for a previous message that is NOT the last sequence number (e.g if receiver has high drop rate) then sender may keep sending packets and receiver will update dropped/total towards the next round of messages because on its side it has already received all messages (next message itself will be preserved.


Part 3: Distance Vector protocol

Usage: 
To start the DV protocol, please use the same command as provided in programming assignment instructions.

$ dvnode <local-port> <neighbor1-port> <loss-rate-1> <neighbor2-port> <loss-rate-2> ... [last]

dvnode.py has a table (dictionary) to keep track of node to distance vector, and next hop (dictionary) to keep track of node to next hop. It also has a set of neighbors. Similar to SR protocol, DV protocol starts with init. It then enters a while loop according to the DV protocol. Upon receiving input, it will parse the dictionary sent by its neighbor and update its own table if necessary. If any changes have been made, it will send changes to all neighbors.

Part 4: Combined Protocol

Usage:

To start, please use same command as provided in programmign assignment instructions.

$ cnnode <local-port> receive <neighbor1-port> <loss-rate-1> <neighbor2-port> <loss-rate-2> ... <neighborM-port> <loss-rate-M> send <neighbor(M+1)-port> <neighbor(M+2)-port> ... <neighborN-port> [last]

cnnode.py combines part 2 and part 3 and hence uses the same overall idea as the descriptions above. Additionally, it sends out changes if any were detected in a 5 second interval, and link descriptions are output every 1 second and probes are sent out every 3 seconds. The message it sends out is the first 10 letters of the alphabet (for probe). 
