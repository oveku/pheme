"""Add Norwegian newspaper sources and create Norwegian News topic on Pheme."""

import httpx
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8020"

SOURCES = [
    {"name": "VG", "url": "https://www.vg.no/rss/feed/", "type": "rss"},
    {
        "name": "Dagbladet",
        "url": "https://www.dagbladet.no/rss/nyheter/",
        "type": "rss",
    },
    {
        "name": "Nettavisen",
        "url": "https://www.nettavisen.no/service/rich-rss?tag=nyheter",
        "type": "rss",
    },
    {"name": "TV2", "url": "https://www.tv2.no/rss/nyheter", "type": "rss"},
    {"name": "Tronderbladet", "url": "https://www.tronderbladet.no/rss", "type": "rss"},
    {
        "name": "Stavanger Aftenblad",
        "url": "https://www.aftenbladet.no/rss",
        "type": "rss",
    },
]

TOPIC = {
    "name": "Norwegian News",
    "keywords": [
        "norge",
        "norsk",
        "norwegian",
        "oslo",
        "bergen",
        "trondheim",
        "stavanger",
        "stortinget",
        "regjeringen",
        "politikk",
        "nyheter",
    ],
    "priority": 85,
    "max_articles": 10,
}


def main():
    client = httpx.Client(base_url=BASE, timeout=10)

    # Create or find topic
    resp = client.post("/api/topics", json=TOPIC)
    if resp.status_code == 201:
        topic = resp.json()
        topic_id = topic["id"]
        print(f"Created topic: {topic['name']} (id={topic_id})")
    else:
        # Topic may already exist, find it
        topics = client.get("/api/topics").json()
        topic_id = next((t["id"] for t in topics if t["name"] == TOPIC["name"]), None)
        if topic_id:
            print(f"Topic already exists: {TOPIC['name']} (id={topic_id})")
        else:
            print(f"Failed to create topic: {resp.status_code} {resp.text}")
            return

    # Add sources and link to topic
    for src in SOURCES:
        payload = {**src, "topic_ids": [topic_id]}
        resp = client.post("/api/sources", json=payload)
        if resp.status_code == 201:
            data = resp.json()
            print(f"  Added: {data['name']} (id={data['id']})")
        else:
            print(f"  Failed: {src['name']} - {resp.status_code} {resp.text}")

    print(f"\nDone! Sources: {len(SOURCES)}, Topic: {TOPIC['name']}")


if __name__ == "__main__":
    main()
