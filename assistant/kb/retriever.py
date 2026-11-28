import re
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent / "docs"

def load_kb_chunks() -> list[dict]:
    chunks = []
    for md_file in sorted(DOCS_DIR.glob("*.md")):
        raw = md_file.read_text(encoding="utf-8")
        meta = {"source_id": md_file.stem.upper(), "title": md_file.stem, "url": ""}
        body = raw
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) == 3:
                for line in parts[1].strip().splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip()
                body = parts[2].strip()
        for idx, section in enumerate(body.split("\n## ")):
            text = section.strip()
            if text:
                chunks.append({
                    "chunk_id": f"{meta['source_id']}_{idx}",
                    "source_id": meta["source_id"],
                    "title": meta["title"],
                    "url": meta["url"],
                    "text": text,
                })
    return chunks

def retrieve_guidance(question: str, top_k: int = 3) -> list[dict]:
    """Keyword + overlap grounded retrieval over vetted CPCB/CAQM/EPA markdown docs."""
    query_tokens = set(re.findall(r"[a-z0-9]+", question.lower()))
    # Expand common Hinglish terms for bilingual retrieval
    hinglish_map = {
        "bachche": "child", "bachchon": "child", "park": "outdoor", "bahar": "outdoor",
        "mask": "n95", "purifier": "hepa", "kamra": "indoor", "heater": "carbon",
        "angithi": "carbon", "gaadi": "transport", "metro": "transport", "khidki": "windows",
    }
    for k, v in hinglish_map.items():
        if k in query_tokens:
            query_tokens.add(v)

    scored = []
    for ch in load_kb_chunks():
        doc_tokens = set(re.findall(r"[a-z0-9]+", ch["text"].lower()))
        overlap = len(query_tokens & doc_tokens)
        if overlap > 0:
            scored.append((overlap, ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored[:top_k]]
