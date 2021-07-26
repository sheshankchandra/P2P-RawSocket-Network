# P2P File Sharing

Simple peer to peer file sharing program in python using raw sockets.
Project done during 3rd year lockdown (May-July 2021).

## Setup
pip install -r requirements.txt

## How to run
1. To run test simulation:
python test_simulation.py

2. To run peer 1 (Alice):
python run_peer.py --id Alice --tcp 6001

3. To run peer 2 (Bob):
python run_peer.py --id Bob --tcp 6002

Inside the peer prompt:
- `peers`: show connected peers
- `share <path>`: share a file
- `networkfiles`: list files in the network
- `download <file_id>`: download file chunks
