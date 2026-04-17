REPLICATION_FACTOR = 2
CHUNK_SIZE = 1024 * 1024  # 1MB
HEARTBEAT_INTERVAL = 5    # seconds
NODE_TIMEOUT = 15         # seconds

COORDINATOR_HOST = "127.0.0.1"
COORDINATOR_PORT = 5000

STORAGE_NODES = [
    {"id": "node1", "host": "127.0.0.1", "port": 5001},
    {"id": "node2", "host": "127.0.0.1", "port": 5002},
    {"id": "node3", "host": "127.0.0.1", "port": 5003},
]
