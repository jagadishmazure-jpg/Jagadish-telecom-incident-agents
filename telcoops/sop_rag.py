"""TF-IDF SOP retriever with citations.

Chunks are (doc, section) pairs parsed from the markdown SOPs. ``retrieve``
returns the top-k chunks with ``<file> §<section>`` citations. When nothing
scores above the threshold it returns an explicit not-found instead of a
weak match.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Hit:
    doc: str
    section: str
    text: str
    score: float

    @property
    def citation(self) -> str:
        return f"{self.doc} §{self.section}"


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def load_chunks(sop_dir: str | Path) -> list[dict]:
    chunks: list[dict] = []
    for path in sorted(Path(sop_dir).glob("*.md")):
        section = ""
        buf: list[str] = []
        title_seen = False
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                title_seen = True
                continue
            m = re.match(r"##\s+(.*)", line)
            if m:
                if buf and title_seen:
                    chunks.append({"doc": path.name, "section": section,
                                   "text": " ".join(buf)})
                section = m.group(1).strip()
                buf = []
            elif line.strip():
                buf.append(line.strip())
        if buf and title_seen:
            chunks.append({"doc": path.name, "section": section,
                           "text": " ".join(buf)})
    return chunks


class SopRetriever:
    def __init__(self, sop_dir: str | Path) -> None:
        self.chunks = load_chunks(sop_dir)
        self._idf = self._build_idf()

    def _build_idf(self) -> dict[str, float]:
        df: dict[str, int] = {}
        for c in self.chunks:
            for tok in set(_tokens(c["text"])):
                df[tok] = df.get(tok, 0) + 1
        n = max(len(self.chunks), 1)
        return {t: math.log(n / d) for t, d in df.items()}

    def _score(self, query: str, text: str) -> float:
        toks = _tokens(text)
        if not toks:
            return 0.0
        tf: dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        score = 0.0
        for t in set(_tokens(query)):
            if t in tf:
                score += (tf[t] / len(toks)) * self._idf.get(t, 0.0)
        return score

    def retrieve(self, query: str, top_k: int = 2,
                 threshold: float = 0.02) -> list[Hit]:
        scored = [(self._score(query, c["text"]), c) for c in self.chunks]
        scored.sort(key=lambda s: -s[0])
        hits = [Hit(doc=c["doc"], section=c["section"], text=c["text"],
                    score=round(s, 4))
                for s, c in scored[:top_k] if s >= threshold]
        return hits
