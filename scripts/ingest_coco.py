"""Load the real COCO transcripts into the proxy traffic table.

The store's own replies ARE the service templates — distillation
(chapter 18) mined synthetic shadow traffic; here it mines a REAL
transcript dump. Each (user turn → the store's actual next reply)
becomes one logged traffic row in domain 'cocoshoes', exactly the shape
distill_traffic.py expects. The store authored its own replacement.
"""
import json
import sqlite3
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COCO = Path.home() / "Downloads" / "coco_shoes_training_dataset.jsonl"
DB = REPO / "data" / "proxy_traffic.sqlite"

sys.path.insert(0, str(REPO))
from gaucho_cache.proxy import SCHEMA

con = sqlite3.connect(DB)
con.executescript(SCHEMA)
con.execute("DELETE FROM traffic WHERE domain='cocoshoes'")
n = 0
for line in open(COCO):
    msgs = json.loads(line)["messages"]
    last_user = None
    for m in msgs:
        if m["role"] == "user":
            last_user = m["content"]
        elif m["role"] == "assistant" and last_user:
            # user turn → the store's real reply = one shadow row
            con.execute(
                "INSERT INTO traffic (domain,ts,last_bot,user_msg,"
                "provider_reply,served_by) VALUES (?,?,?,?,?,'provider')",
                ("cocoshoes", time.time(), None, last_user, m["content"]))
            n += 1
            last_user = None
con.commit()
con.close()
print(f"ingested {n} real (user→store-reply) pairs into domain 'cocoshoes'")
