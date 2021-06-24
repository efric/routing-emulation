Eric Feng,
ef2648

Part 2: Selective Repeat protocol


Usage:
To start the SR protocol, please use the same command as provided in the programming assignment instructions. In other words,

$ ./srnode.py <self-port> <peer-port> <window-size> [ -d <value-of-n> | -p <value-of-p>]

where d represents drop packets deterministically and p represents drop packets probabilistically. p must be a number between 0-1 (where 0 means never drop, 1 means always drop) and d must be a nonnegative number. 

Implementation details:
The program begins with the function 'init' which is used to filter out improper user input and exit early. Following that, we enter 'init_srp' which is where the program actually begins. We initialize two threads. One calls 'do_listen', which is the main thread responsible for listening to responses (ACK, etc) and the other, 'do_send' for sending the message. 

do_send maintains a sliding window across the message input by the user; the entire message is interpreted as the buffer for convenience, though we may only send characters within the appropriate window. The start/end of the window is increased whenever it receives an appropriate ACK from the receiver according to SR protocol. Each letter is sent in a separate message and is prepended by the sequence number. do_send drops/sends messages according to -d/-p value then enters a timeout thread. The timeout thread sleeps for 0.5 seconds and wakes up to check if the sequence number has been acknowledged by listen thread. If the sequence number has not been acknowledged yet, it will resend the message then sleep again for 0.5 seconds. On the last character, we append the packet by the null terminator \0 to let the receiver side know we are done. When we have received ACK for all characters, we will join all still-existing threads.

do_listen is responsible both for parsing ACKs on sender side and parsing messages on the receiver side. On ACK, we add the sequence number to an acknowledged set and update the sender window. On receiver side, we extract the character and sequence number and send ACK back to sender side according to -d/-p whilst updating the receiver sliding window. Out of order messages are buffered (buffer is an empty list of characters) and ACKs are dropped based on -d/-p value input by the user at the start of the program.

This program is bidirectional and thus both nodes may send/receive messages to each other. Messages must be sent after the previous message has arrived to not mess up the window on either side.

Edge case: If a receiver receives the complete message (i.e received \0 in a message and all other characters before it) but the sender hasn't received ack for a message that is NOT the last sequence number (e.g the message is "hello" and "hel_o" has been ACK'd but the last 'l' hasn't yet) then the sender may send packets requesting ACK for it and receiver will update its dropped/total for this message towards the next round of messages between the two nodes because on its side it has already received all characters. However, this does not pollute the next message content itself as the new message will overwrite the receiver buffer in the next round.


Part 3: Distance Vector protocol

Usage: 
To start the DV protocol, please use the same command as provided in programming assignment instructions.

$ ./dvnode.py <local-port> <neighbor1-port> <loss-rate-1> <neighbor2-port> <loss-rate-2> ... [last]

where last is an optional argument which will kick start the algorithm. local-port is the port number of the initializing node and neighbor-port, loss-rate are pairs describing the relationship between the initializing node and its neighbor and the link they share. 

Implementation details:
THe program begins with the function 'init' which is used to filter improper input (port out of range, etc) and then parses the user input of neighbor port, loss rate pairs. At this point, we initialize several data structures. dvnode.py has a dictionary called rt (routing table) which has key: port number and value loss rate. Each node also has a set that keeps track of its direct neighbors. Then, each node listens for messages. The node which received 'last' as user input will send out a message containg its routing table to its direct neighbors to kick start the protocol. When neighbors receive input, it will parse the dictionary sent by its neighbor and update its own table. If any changes have been made, or if its the node has just been contacted for the first time, it will send out its routing table to all its neighbors. Distance vectors within the routing table are updated by the minimum between the cost of the link and distance vector of the pertaining node and the current distance vector in the current routing table according to the bellman-ford algorithm. 

Part 4: Combined Protocol

Usage:

To start, please use same command as provided in programming assignment instructions.

$ ./cnnode.py <local-port> receive <neighbor1-port> <loss-rate-1> <neighbor2-port> <loss-rate-2> ... <neighborM-port> <loss-rate-M> send <neighbor(M+1)-port> <neighbor(M+2)-port> ... <neighborN-port> [last]

where last is an optional argument which will kick start the algorithm. local-port is the port number of the initializing node and neighbor-port, loss-rate are pairs describing the relationship between the initializing node and its neighbor and the link they share. The pairs are prepended by 'receive' or 'send' keyword describing who they are probe receivers/senders for. 

Implementation details:
The program begins with the function 'init' which again is used to filter improper input and parsing user input. Both ports in the sending list and receiving list are put inside a neighbors set, and their routing table value is initialized to 0. A separate dictionary of dictionaries is used to keep track of SR protocol details for nodes in the sending/receiving list. This contains details such as the status of the sliding window, number of dropped packets, total packets, acknowledged sequence numbers, etc that we described in part 2 of the assignment. From here, we initialize several threads. One (probe) is responsible for sending out probe messages to update the loss rate every 3 seconds. One (update_timer) is used to detect changes in the routing table from the SR protocol. It sleeps for 5 seconds at a time, and if there were any changes, we send the pertaining node's routing table to all its neighbors (updates are also sent out when new information is received from 'listen'). Another thread (status) is used to output the loss rate of a link to standard output every 1 second. Finally, we enter 'listen' functon, which listens for messages then splits off a new thread to deal with it each time.

When 'listen' receives a new message, it will check to see what type of message it is. There are 3 different types of messages: ACK from a receiver (as a sender), probe data from a sender (as a receiver) or routing table information from a neighbor. For routing table information, it is updated the same way as described in part 3. For ACK and probe data, it is updated the same way as descibed in part 2. 

The probe message that nodes in the senders list send is the first 10 characters of the alphabet (abcdefghij) and the window size is always 5. When the last character is received (in timeout), the routing table of the sender's node is updated (if there is change) and it will then send this table to all neighbors. 

To start sending probe messages, probe receivers must first tell the probe senders the link loss rate in an initial contact message. This is included as part of the initial routing table information when the probe receiver is first turned on (when it first received a message and then sending out its routing table information for the first time). The initial loss rate of a particular link (-p value for SR protocol) is embedded in the dictionary as the value for a key -1. 
