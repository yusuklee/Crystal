"""crystal/data가 갖춰져 있으면 실데이터, 아니면 crystal/web/sample. 유저·피드는 줄 오프셋으로 찾는다."""
import hashlib
import json
import os
import re
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REAL_DIR = os.path.join(ROOT, "crystal", "data")
SAMPLE_DIR = os.path.join(HERE, "sample")
CACHE_DIR = os.path.join(HERE, "_cache")
PLACEHOLDER = "Analyzing context..."
REAL_SEED_USER = "25376730"  # 2026-10-21 CROWN 피드 기준 재선정 (_workspace/11_seed.json 1순위)
_UID = re.compile(rb'"user_id":\s*"([^"]+)"')

try:
    from crystal.common import is_displayable
except Exception:
    def is_displayable(title, body):
        b = (body or "").strip()
        return b != "" and b != (title or "").strip() and not (b.startswith(".css") or "{display:" in b[:300])
try:
    from crystal.recsys.stats import label_dist, history_dist
except Exception:
    def label_dist(article_ids, articles_by_id, label_field="final_label"):
        labels = [articles_by_id[a][label_field] for a in article_ids
                  if a in articles_by_id and articles_by_id[a].get(label_field) is not None]
        n_fake = sum(1 for l in labels if l == 1)
        total = len(labels)
        return {"true": (total - n_fake) / total if total else 0.0, "fake": n_fake / total if total else 0.0,
                "n_true": total - n_fake, "n_fake": n_fake, "total": total}

    def history_dist(history, articles_by_id, days=None, label_field="final_label"):
        if days is not None and history:
            cut = history[-1]["time"] - days * 86400
            history = [h for h in history if h["time"] >= cut]
        return label_dist(list(dict.fromkeys(h["article_id"] for h in history)), articles_by_id, label_field)


def _line_index(path):
    st = os.stat(path)
    cpath = os.path.join(CACHE_DIR, hashlib.md5(path.encode("utf-8")).hexdigest()[:10] + "-" + os.path.basename(path) + ".idx.json")
    if st.st_size > 5_000_000 and os.path.exists(cpath):
        with open(cpath, encoding="utf-8") as f:
            c = json.load(f)
        if c["size"] == st.st_size and c["mtime"] == st.st_mtime:
            return c["offsets"]
    offsets, pos = {}, 0
    with open(path, "rb") as f:
        for line in f:
            m = _UID.search(line[:256])
            if m:
                offsets[m.group(1).decode("utf-8")] = pos
            pos += len(line)
    if st.st_size > 5_000_000:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cpath, "w", encoding="utf-8") as f:
            json.dump({"size": st.st_size, "mtime": st.st_mtime, "offsets": offsets}, f)
    return offsets


def _real_ready():
    for name in ("articles.jsonl", "users.jsonl", "feeds.jsonl"):
        if not os.path.exists(os.path.join(REAL_DIR, name)):
            return False, f"{name} 없음"
    with open(os.path.join(REAL_DIR, "articles.jsonl"), encoding="utf-8") as f:
        for line in f:
            if '"split": "test"' in line and '"keywords": [{' in line:
                return True, "test 기사에 keywords 있음"
    return False, "test 기사에 keywords 없음"


class Store:
    def __init__(self, data_dir, source, reason):
        self.dir, self.source, self.reason = data_dir, source, reason
        self.articles = {}
        with open(os.path.join(data_dir, "articles.jsonl"), encoding="utf-8") as f:
            for line in f:
                a = json.loads(line)
                self.articles[a["article_id"]] = a
        self.pool = [a for a in self.articles.values() if a.get("split", "test") == "test" and is_displayable(a.get("title"), a.get("body"))]
        self.users_path = os.path.join(data_dir, "users.jsonl")
        self.feeds_path = os.path.join(data_dir, "feeds.jsonl")
        self.user_off = _line_index(self.users_path)
        self.feed_off = _line_index(self.feeds_path)
        self.cache = {}
        p = os.path.join(data_dir, "rationale_cache.jsonl")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                for line in f:
                    r = json.loads(line)
                    self.cache[(r["article_id"], r["kind"], r["key"])] = r["text"]
        self.clicks = {}

    @staticmethod
    def _read(path, off):
        with open(path, "rb") as f:
            f.seek(off)
            return json.loads(f.readline().decode("utf-8"))

    def default_user(self):
        env = os.environ.get("CRYSTAL_SEED_USER")
        for uid in (env, REAL_SEED_USER):
            if uid and uid in self.feed_off:
                return uid
        return next(iter(self.feed_off), None)

    def history(self, uid):
        if uid not in self.user_off:
            return None
        return self._read(self.users_path, self.user_off[uid])["history"] + self.clicks.get(uid, [])

    def feed(self, uid):
        if uid not in self.feed_off:
            return None
        return self._read(self.feeds_path, self.feed_off[uid])["feed"]

    def log_click(self, uid, aid):
        self.clicks.setdefault(uid, []).append({"article_id": aid, "time": int(time.time())})

    def stats(self, uid, page_ids):
        hist = self.history(uid) or []
        return {"weekly": history_dist(hist, self.articles, 7),
                "overall": history_dist(hist, self.articles, None),
                "feed": label_dist(page_ids, self.articles)}

    def lookup(self, article_id, kind, key):
        a = self.articles.get(article_id)
        if a:
            if kind == "keyword" and (a.get("rationales") or {}).get(key):
                return a["rationales"][key], "article"
            if kind == "verdict" and a.get("verdict_rationale"):
                return a["verdict_rationale"], "article"
            if kind == "contrast":
                for c in a.get("counterparts") or []:
                    if c.get("article_id") == key and c.get("claim_contrast"):
                        return c["claim_contrast"], "article"
        for k in ((article_id, kind, key), (article_id, kind, "")):
            t = self.cache.get(k)
            if t:
                if kind == "contrast" and isinstance(t, str):
                    try:
                        t = json.loads(t)
                    except ValueError:
                        pass
                if kind == "contrast" and not (isinstance(t, dict) and "this" in t):
                    continue  # contrast-v1 형식(fake/verified) 캐시는 무시
                return t, "cache"
        return None, "pending"

    def get_rationale(self, article_id, kind, key):
        """캐시 조회 자리. 실제 Gemini 호출은 rationale 모듈이 여기에 붙인다."""
        t, status = self.lookup(article_id, kind, key)
        if t is not None:
            return t, status
        if self.source == "real":
            try:
                from crystal.rationale.online import get_rationale
                t = get_rationale(article_id, kind, key, self.articles)
                self.cache[(article_id, kind, key)] = t if isinstance(t, str) else json.dumps(t, ensure_ascii=False)
                return t, "online"
            except Exception:
                pass
        if kind == "contrast":
            return {"this": PLACEHOLDER, "related": PLACEHOLDER}, "pending"
        return PLACEHOLDER, "pending"


def load_store():
    mode = os.environ.get("CRYSTAL_DATA", "auto")
    if mode == "sample":
        return Store(SAMPLE_DIR, "sample", "CRYSTAL_DATA=sample")
    ok, reason = _real_ready()
    if mode == "real" or ok:
        return Store(REAL_DIR, "real", reason if ok else f"CRYSTAL_DATA=real 강제 ({reason})")
    return Store(SAMPLE_DIR, "sample", reason)
