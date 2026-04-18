# Distributed File System with Fault Tolerance

## Architecture

```
Client --> Coordinator (port 5000)
                |
    +-----------+-----------+
    |           |           |
 Node1       Node2       Node3
(5001)      (5002)      (5003)
```

## Setup

```bash
pip install -r requirements.txt
```

## Run

Open 4 terminals:

**Terminal 1 - Coordinator:**
```bash
python coordinator.py
```

**Terminal 2, 3, 4 - Storage Nodes:**
```bash
python storage_node.py node1
python storage_node.py node2
python storage_node.py node3
```

## Client Commands

```bash
# Upload a file
python client.py upload myfile.txt

# Download a file
python client.py download myfile.txt output.txt

# Delete a file
python client.py delete myfile.txt

# Check system status
python client.py status
```

## Fault Tolerance

- Each file chunk is replicated across 2 nodes (REPLICATION_FACTOR=2)
- Coordinator sends heartbeats every 5 seconds
- If a node is silent for 15 seconds, it's marked as DOWN
- Coordinator automatically re-replicates lost chunks to alive nodes
- Client always tries all replica nodes before failing

## Configuration (config.py)

| Setting | Default | Description |
|---|---|---|
| REPLICATION_FACTOR | 2 | Copies per chunk |
| CHUNK_SIZE | 1MB | Size per chunk |
| HEARTBEAT_INTERVAL | 5s | Heartbeat frequency |
| NODE_TIMEOUT | 15s | Time before node marked dead |
