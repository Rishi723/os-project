import time
import threading
import requests
import os
import json
from flask import Flask, request, jsonify
from config import REPLICATION_FACTOR, HEARTBEAT_INTERVAL, NODE_TIMEOUT, COORDINATOR_PORT, STORAGE_NODES

app = Flask(__name__)
METADATA_FILE = "metadata.json"

# metadata: {filename: [{chunk_id, nodes:[node_id,...]}]}
file_metadata = {}
node_status = {n["id"]: {"info": n, "last_seen": time.time(), "alive": True} for n in STORAGE_NODES}
lock = threading.Lock()

# 🔷 Load metadata at startup
def load_metadata():
    global file_metadata
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r") as f:
                file_metadata = json.load(f)
            print("[COORDINATOR] Metadata loaded successfully")
        except Exception as e:
            print(f"[COORDINATOR] Failed to load metadata: {e}")
            file_metadata = {}
    else:
        file_metadata = {}


# 🔷 Save metadata to disk
def save_metadata():
    try:
        with open(METADATA_FILE, "w") as f:
            json.dump(file_metadata, f, indent=2)
    except Exception as e:
        print(f"[COORDINATOR] Failed to save metadata: {e}")

def get_alive_nodes():
    return [v["info"] for v in node_status.values() if v["alive"]]


def pick_nodes(count):
    alive = get_alive_nodes()
    if len(alive) < count:
        count = len(alive)
    return alive[:count]


def monitor_nodes():
    while True:
        time.sleep(HEARTBEAT_INTERVAL)
        now = time.time()
        with lock:
            for nid, data in node_status.items():
                was_alive = data["alive"]
                data["alive"] = (now - data["last_seen"]) < NODE_TIMEOUT
                if was_alive and not data["alive"]:
                    print(f"[COORDINATOR] Node {nid} is DOWN. Triggering re-replication.")
                    threading.Thread(target=re_replicate, args=(nid,), daemon=True).start()


def re_replicate(failed_node_id):
    with lock:
        for filename, chunks in file_metadata.items():
            for chunk in chunks:
                if failed_node_id in chunk["nodes"]:
                    chunk["nodes"].remove(failed_node_id)
                    alive = get_alive_nodes()
                    candidates = [n for n in alive if n["id"] not in chunk["nodes"]]
                    if not candidates:
                        continue
                    # fetch chunk from existing node and push to new node
                    source_id = chunk["nodes"][0] if chunk["nodes"] else None
                    if not source_id:
                        continue
                    source = node_status[source_id]["info"]
                    target = candidates[0]
                    try:
                        r = requests.get(f"http://{source['host']}:{source['port']}/chunk/{chunk['chunk_id']}")
                        if r.status_code == 200:
                            requests.post(
                                f"http://{target['host']}:{target['port']}/chunk/{chunk['chunk_id']}",
                                data=r.content,
                                headers={"Content-Type": "application/octet-stream"}
                            )
                            chunk["nodes"].append(target["id"])
                            print(f"[COORDINATOR] Re-replicated chunk {chunk['chunk_id']} to {target['id']}")
                    except Exception as e:
                        print(f"[COORDINATOR] Re-replication error: {e}")
    save_metadata()  # ✅ persist changes
                    


@app.route("/heartbeat/<node_id>", methods=["POST"])
def heartbeat(node_id):
    with lock:
        if node_id in node_status:
            node_status[node_id]["last_seen"] = time.time()
            node_status[node_id]["alive"] = True
    return jsonify({"status": "ok"})


@app.route("/register_chunk", methods=["POST"])
def register_chunk():
    data = request.json
    filename = data["filename"]
    chunk_id = data["chunk_id"]
    nodes = data["nodes"]
    with lock:
        if filename not in file_metadata:
            file_metadata[filename] = []
        file_metadata[filename].append({"chunk_id": chunk_id, "nodes": nodes,"hash": data["hash"]   })    # ✅ NEW
        save_metadata()  # ✅ persist
    return jsonify({"status": "registered"})


@app.route("/locate/<filename>", methods=["GET"])
def locate(filename):
    with lock:
        chunks = file_metadata.get(filename)
    if not chunks:
        return jsonify({"error": "File not found"}), 404
    return jsonify({"filename": filename, "chunks": chunks})


@app.route("/allocate", methods=["POST"])
def allocate():
    data = request.json
    nodes = pick_nodes(REPLICATION_FACTOR)
    if not nodes:
        return jsonify({"error": "No alive nodes"}), 503
    return jsonify({"nodes": nodes})


@app.route("/delete/<filename>", methods=["DELETE"])
def delete_file(filename):
    with lock:
        chunks = file_metadata.pop(filename, None)
        save_metadata() # ✅ save after deletion
    if not chunks:
        return jsonify({"error": "File not found"}), 404
    for chunk in chunks:
        for nid in chunk["nodes"]:
            node = node_status.get(nid)
            if node and node["alive"]:
                try:
                    requests.delete(f"http://{node['info']['host']}:{node['info']['port']}/chunk/{chunk['chunk_id']}")
                except Exception:
                    pass
    return jsonify({"status": "deleted"})


@app.route("/status", methods=["GET"])
def status():
    with lock:
        return jsonify({
            "nodes": {nid: {"alive": d["alive"], "host": d["info"]["host"], "port": d["info"]["port"]}
                      for nid, d in node_status.items()},
            "files": {f: len(c) for f, c in file_metadata.items()}
        })


if __name__ == "__main__":
    load_metadata() # ✅ load on startup
    threading.Thread(target=monitor_nodes, daemon=True).start()
    print(f"[COORDINATOR] Running on port {COORDINATOR_PORT}")
    app.run(host="0.0.0.0", port=COORDINATOR_PORT)
