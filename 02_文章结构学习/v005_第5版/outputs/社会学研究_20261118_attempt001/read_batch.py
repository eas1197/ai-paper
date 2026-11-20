"""Read page-addressed source snippets from the frozen Zotero inventory."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def print_batch(first, last, compact=False):
    articles = [a for a in load(ROOT / "馆藏清单.json")["articles"] if a.get("pdf_path")]
    for number, article in enumerate(articles, 1):
        if number < first or number > last:
            continue
        paper = article["paper_id"]
        print(f"{number:02} {paper} {article['title']} ({article['year']}年第{article['issue']}期)")
        source = load(ROOT / "work" / f"{paper}.json")
        blocks = source["blocks"]
        print("节", " → ".join(f"{h['pdf_page']}:{h['heading'][:34]}" for h in article["section_heading_candidates"] if h["level"] == 1))
        abstract = next((b for b in blocks if b["section"] == "摘要" or (b["start_page"] == 1 and b["text"].startswith(("中文摘要", "摘要:", "提要:")))), None)
        if abstract:
            print(f"摘要 p{abstract['start_page']} {abstract['id']}: {abstract['text'][:330 if compact else 460]}")
        else:
            print("摘要未自动识别")
        if compact:
            print()
            continue
        seen = set()
        for block in blocks:
            title = block["section"]
            if title == "摘要" or title in seen or len(block["text"]) < 42:
                continue
            seen.add(title)
            print(f"p{block['start_page']} {block['id']} {block['text'][:110]}")
        print()


if __name__ == "__main__":
    print_batch(*map(int, sys.argv[1:3]), compact="--compact" in sys.argv[3:])
