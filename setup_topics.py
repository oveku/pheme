"""Create topics and link sources on a running Pheme instance."""

import httpx
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8020"

TOPICS = [
    {
        "name": "AI & Machine Learning",
        "keywords": [
            "artificial intelligence",
            "machine learning",
            "deep learning",
            "neural network",
            "LLM",
            "GPT",
            "transformer",
            "AI model",
            "training",
            "inference",
            "ollama",
        ],
        "priority": 90,
        "max_articles": 5,
    },
    {
        "name": "Homelab & Self-Hosting",
        "keywords": [
            "homelab",
            "self-hosted",
            "docker",
            "raspberry pi",
            "proxmox",
            "home server",
            "NAS",
            "container",
            "kubernetes",
            "k3s",
        ],
        "priority": 80,
        "max_articles": 5,
    },
    {
        "name": "Programming & Python",
        "keywords": [
            "python",
            "programming",
            "developer",
            "software engineering",
            "fastapi",
            "rust",
            "typescript",
            "open source",
            "github",
            "coding",
        ],
        "priority": 70,
        "max_articles": 5,
    },
    {
        "name": "Cybersecurity",
        "keywords": [
            "security",
            "vulnerability",
            "hack",
            "zero-day",
            "malware",
            "ransomware",
            "privacy",
            "encryption",
            "CVE",
            "breach",
        ],
        "priority": 60,
        "max_articles": 3,
    },
]

# Source-to-topic mapping (source name -> list of topic names)
SOURCE_TOPICS = {
    "TLDR AI": ["AI & Machine Learning"],
    "TLDR Tech": ["AI & Machine Learning", "Programming & Python", "Cybersecurity"],
    "Hacker News (Best)": [
        "AI & Machine Learning",
        "Programming & Python",
        "Homelab & Self-Hosting",
    ],
    "r/MachineLearning": ["AI & Machine Learning"],
    "r/Python": ["Programming & Python"],
    "r/selfhosted": ["Homelab & Self-Hosting"],
    "r/homelab": ["Homelab & Self-Hosting"],
    "Ars Technica": ["AI & Machine Learning", "Cybersecurity"],
    "The Verge": ["AI & Machine Learning"],
}


def main():
    client = httpx.Client(base_url=BASE, timeout=10)

    # Create topics
    topic_map = {}  # name -> id
    for t in TOPICS:
        resp = client.post("/api/topics", json=t)
        if resp.status_code == 201:
            data = resp.json()
            topic_map[data["name"]] = data["id"]
            print(f"  Created topic: {data['name']} (id={data['id']})")
        else:
            print(f"  Failed to create topic {t['name']}: {resp.text}")

    # Get existing sources
    sources = client.get("/api/sources").json()

    # Link sources to topics
    for src in sources:
        topic_names = SOURCE_TOPICS.get(src["name"], [])
        if topic_names:
            topic_ids = [topic_map[n] for n in topic_names if n in topic_map]
            if topic_ids:
                resp = client.put(
                    f"/api/sources/{src['id']}", json={"topic_ids": topic_ids}
                )
                if resp.status_code == 200:
                    print(f"  Linked {src['name']} -> {topic_names}")
                else:
                    print(f"  Failed to link {src['name']}: {resp.text}")

    print("\nDone! Topics and links created.")
    print(f"Topics: {client.get('/api/topics').json()}")


if __name__ == "__main__":
    main()
