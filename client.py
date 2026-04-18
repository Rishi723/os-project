import os
import math
import requests
import hashlib # ✅ NEW
from config import COORDINATOR_HOST, COORDINATOR_PORT, CHUNK_SIZE

BASE = f"http://{COORDINATOR_HOST}:{COORDINATOR_PORT}"


def upload(filepath):
    filename = os.path.basename(filepath)
    file_size = os.path.getsize(filepath)
    total_chunks = math.ceil(file_size / CHUNK_SIZE)

    with open(filepath, "rb") as f:
        for i in range(total_chunks):
            chunk_data = f.read(CHUNK_SIZE)
            chunk_hash = hashlib.sha256(chunk_data).hexdigest() # ✅ NEW
            chunk_id = f"{filename}_chunk{i}"

            # Ask coordinator which nodes to use
            r = requests.post(f"{BASE}/allocate", json={"filename": filename})
            if r.status_code != 200:
                print(f"[CLIENT] Allocation failed: {r.json()}")
                return

            nodes = r.json()["nodes"]
            stored_on = []

            for node in nodes:
                try:
                    resp = requests.post(
                        f"http://{node['host']}:{node['port']}/chunk/{chunk_id}",
                        data=chunk_data,
                        headers={"Content-Type": "application/octet-stream"}
                    )
                    if resp.status_code == 200:
                        stored_on.append(node["id"])
                except Exception as e:
                    print(f"[CLIENT] Failed to store on {node['id']}: {e}")

            # Register chunk with coordinator
            requests.post(f"{BASE}/register_chunk", json={
                "filename": filename,
                "chunk_id": chunk_id,
                "nodes": stored_on,
                 "hash": chunk_hash  # ✅ NEW
            })
            print(f"[CLIENT] Uploaded chunk {i+1}/{total_chunks} -> {stored_on}")

    print(f"[CLIENT] Upload complete: {filename}")


def download(filename, output_path):
    r = requests.get(f"{BASE}/locate/{filename}")
    if r.status_code != 200:
        print(f"[CLIENT] File not found: {filename}")
        return

    chunks = sorted(r.json()["chunks"], key=lambda c: int(c["chunk_id"].split("_chunk")[-1]))

    with open(output_path, "wb") as out:
        for chunk in chunks:
            data = None
            for node_id in chunk["nodes"]:
                # Get node info from coordinator status
                status = requests.get(f"{BASE}/status").json()
                node = status["nodes"].get(node_id)
                if not node or not node["alive"]:
                    continue
                try:
                    resp = requests.get(f"http://{node['host']}:{node['port']}/chunk/{chunk['chunk_id']}")
                    if resp.status_code == 200:
                        data = resp.content
                        calculated_hash = hashlib.sha256(data).hexdigest()
                        if calculated_hash != chunk["hash"]:
                            print(f"[CLIENT] Corruption detected in {chunk['chunk_id']} from {node_id}")
                            continue  
                        break
                except Exception:
                    continue
            if data is None:
                print(f"[CLIENT] Could not retrieve chunk {chunk['chunk_id']}")
                return
            out.write(data)

    print(f"[CLIENT] Download complete: {output_path}")


def delete(filename):
    r = requests.delete(f"{BASE}/delete/{filename}")
    print(f"[CLIENT] Delete response: {r.json()}")


def status():
    r = requests.get(f"{BASE}/status")
    import json
    print(json.dumps(r.json(), indent=2))


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python client.py upload <filepath>")
        print("  python client.py download <filename> <output_path>")
        print("  python client.py delete <filename>")
        print("  python client.py status")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "upload" and len(sys.argv) == 3:
        upload(sys.argv[2])
    elif cmd == "download" and len(sys.argv) == 4:
        download(sys.argv[2], sys.argv[3])
    elif cmd == "delete" and len(sys.argv) == 3:
        delete(sys.argv[2])
    elif cmd == "status":
        status()
    else:
        print("Invalid command or missing arguments.")  #done
