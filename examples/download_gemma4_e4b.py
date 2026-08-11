"""Download the official Gemma 4 E4B IT Orbax checkpoint from the public
gs://gemma-data bucket over plain HTTPS (bucket is public; no credentials).

Layout mirrors the bucket so orbax can open the directory directly.
"""

import concurrent.futures as cf
import json
import os
import sys
import time
import urllib.parse
import urllib.request

BUCKET = "gemma-data"
PREFIX = "checkpoints/gemma4-e4b-it"
DEST = os.environ.get("GEMMA_CKPT_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "gemma4-e4b-it"))
TOKENIZER_OBJ = "tokenizers/tokenizer_gemma4.model"
TOKENIZER_DEST = os.environ.get("GEMMA_TOKENIZER", os.path.join(os.path.dirname(DEST), "tokenizer_gemma4.model"))

CHUNK = 16 * 1024 * 1024


def list_objects():
    objs = []
    page_token = None
    while True:
        url = (
            f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o?"
            f"prefix={urllib.parse.quote(PREFIX, safe='')}&maxResults=1000"
        )
        if page_token:
            url += f"&pageToken={page_token}"
        with urllib.request.urlopen(url) as r:
            data = json.load(r)
        objs.extend(data.get("items", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return objs


def download(name, size, dest_path):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    if os.path.exists(dest_path) and os.path.getsize(dest_path) == size:
        return name, size, 0.0, "skip"
    url = f"https://storage.googleapis.com/{BUCKET}/{urllib.parse.quote(name)}"
    tmp = dest_path + ".part"
    t0 = time.time()
    for attempt in range(5):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
                while True:
                    buf = r.read(CHUNK)
                    if not buf:
                        break
                    f.write(buf)
            got = os.path.getsize(tmp)
            if got != size:
                raise IOError(f"size mismatch {got} != {size}")
            os.replace(tmp, dest_path)
            return name, size, time.time() - t0, "ok"
        except Exception as e:  # noqa: BLE001
            if attempt == 4:
                return name, size, time.time() - t0, f"FAIL: {e}"
            time.sleep(5 * (attempt + 1))


def main():
    objs = list_objects()
    tasks = []
    for o in objs:
        name = o["name"]
        size = int(o["size"])
        if name.endswith("_$folder$"):
            continue
        rel = name[len(PREFIX) :].lstrip("/")
        dest = os.path.join(DEST, *rel.split("/"))
        tasks.append((name, size, dest))
    # tokenizer
    tok_url = (
        f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o/"
        f"{urllib.parse.quote(TOKENIZER_OBJ, safe='')}"
    )
    with urllib.request.urlopen(tok_url) as r:
        tok_meta = json.load(r)
    tasks.append((TOKENIZER_OBJ, int(tok_meta["size"]), TOKENIZER_DEST))

    total = sum(t[1] for t in tasks)
    print(f"{len(tasks)} files, {total/1e9:.2f} GB total", flush=True)
    done_bytes = 0
    t0 = time.time()
    failures = 0
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(download, *t) for t in tasks]
        for fut in cf.as_completed(futs):
            name, size, dt, status = fut.result()
            done_bytes += size
            rate = size / dt / 1e6 if dt > 0 else 0
            print(
                f"[{done_bytes/1e9:7.2f}/{total/1e9:.2f} GB] {status:5s} "
                f"{name.split('/')[-1][:40]:42s} {size/1e6:9.1f} MB "
                f"{rate:7.1f} MB/s",
                flush=True,
            )
            if status.startswith("FAIL"):
                failures += 1
    print(
        f"DONE in {time.time()-t0:.0f} s, failures={failures}",
        flush=True,
    )
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
