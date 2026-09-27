import socket
import json
import sys

# Implemented the Manager's state tracking first,
# it just needs to remember who is registered
registered_peers = []

def start_manager(port):
    # Create UDP socket 
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', port))
    
    print(f"Manager started on port {port}. Waiting for peers...")

    while True:
        # Listen for any incoming UDP message
        data, addr = sock.recvfrom(4096)
        msg = json.loads(data.decode())
        
        # COMMAND: register
        if msg['cmd'] == 'register':
            peer_info = {'ip': addr[0], 'port': msg['peer_port'], 'state': 'Free'}
            registered_peers.append(peer_info)
            print(f"-> Registered new peer at {addr[0]}:{msg['peer_port']}")
            
        # COMMAND: setup-dht
        elif msg['cmd'] == 'setup-dht':
            n = msg['n']
            print(f"-> Setup-DHT requested for {n} peers.")
            
            if len(registered_peers) < n:
                print("Not enough peers registered!")
                continue
                
            # Select the first n peers and change their state
            selected_peers = registered_peers[:n]
            for p in selected_peers:
                p['state'] = 'InDHT'
                
            # Send the list of selected peers back to the Leader (the one who asked)
            response = {'cmd': 'setup-response', 'peers': selected_peers}
            sock.sendto(json.dumps(response).encode(), addr)
            
        # COMMAND: dht-complete
        elif msg['cmd'] == 'dht-complete':
            print("-> SUCCESS: DHT Setup Complete!")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python manager.py <manager_port>")
    else:
        start_manager(int(sys.argv[1]))