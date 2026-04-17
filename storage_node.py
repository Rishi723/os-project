import os
import sys
import threading
import time
import requests
from flask import Flask, request, jsonify, send_file
from config import COORDINATOR_HOST, COORDINATOR_PORT, HEARTBEAT_INTERVAL, STORAGE_NODES

app = Flask(__name__)

NODE_ID = None
NODE_PORT = None
STORAGE_DIR = None


def heartbeat_loop():
    url = f"http://{COORDINATOR_HOST}:{COORDINATOR_PORT}/heartbeat/{NODE_ID}"
    while True:
        try:
            requests.post(url, timeout=3)
        except Exception:
            pass
        time.sleep(HEARTBEAT_INTERVAL)


@app.route("/chunk/<chunk_id>", methods=["POST"])
def store_chunk(chunk_id):
    path = os.path.join(STORAGE_DIR, chunk_id)
    with open(path, "wb") as f:
        f.write(request.data)
    return jsonify({"status": "stored", "chunk_id": chunk_id})


@app.route("/chunk/<chunk_id>", methods=["GET"])
def get_chunk(chunk_id):
    path = os.path.join(STORAGE_DIR, chunk_id)
    if not os.path.exists(path):
        return jsonify({"error": "Chunk not found"}), 404
    return send_file(path, mimetype="application/octet-stream")


@app.route("/chunk/<chunk_id>", methods=["DELETE"])
def delete_chunk(chunk_id):
    path = os.path.join(STORAGE_DIR, chunk_id)
    if os.path.exists(path):
        os.remove(path)
    return jsonify({"status": "deleted"})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"node_id": NODE_ID, "status": "alive"})


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python storage_node.py <node_id>")
        sys.exit(1)

    NODE_ID = sys.argv[1]
    node_conf = next((n for n in STORAGE_NODES if n["id"] == NODE_ID), None)
    if not node_conf:
        print(f"Unknown node id: {NODE_ID}")
        sys.exit(1)

    NODE_PORT = node_conf["port"]
    STORAGE_DIR = f"storage_{NODE_ID}"
    os.makedirs(STORAGE_DIR, exist_ok=True)

    threading.Thread(target=heartbeat_loop, daemon=True).start()
    print(f"[{NODE_ID}] Storage node running on port {NODE_PORT}")
    app.run(host="0.0.0.0", port=NODE_PORT)
