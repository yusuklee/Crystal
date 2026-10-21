"""웹 온라인 호출: 캐시에 없으면 그 자리에서 생성해 캐시에 더한다 (PRISM의 'Analyzing context...')."""
import json

from crystal.rationale import core

_cache = None
_llm = None
_articles = None


def _state(articles):
    global _cache, _llm, _articles
    if _cache is None:
        _cache = core.Cache()
    if _llm is None:
        _llm = core.Gemini()
    if articles is None:
        if _articles is None:
            _articles = core.load_articles()
        articles = _articles
    return _cache, _llm, articles


def get_rationale(article_id, kind, key, articles=None):
    """kind: keyword(key=phrase) / verdict(key="") / contrast(key=상대 article_id). 반환: str, contrast는 dict."""
    cache, llm, articles = _state(articles)
    hit = cache.get(article_id, kind, key)
    if hit is not None and kind == "contrast":
        hit = json.loads(hit)
        if not core.contrast_ok(hit):
            hit = None  # contrast-v1 형식(fake/verified)은 다시 생성
    if hit is not None:
        return hit
    a = articles[article_id]
    stats = core.new_stats()
    if kind == "keyword":
        kws = [k for k in core.unique_phrases(a) if k["phrase"] == key]
        if not kws:
            raise KeyError(f"phrase not in keywords: {key}")
        out = core.gen_keywords(llm, cache, a, kws, articles, stats)
        text = out.get(key)
    elif kind == "verdict":
        text = core.gen_verdict(llm, cache, a, articles, stats)
    elif kind == "contrast":
        text = core.gen_contrast(llm, cache, a, articles[key], stats)
    else:
        raise ValueError(kind)
    if text is None:
        raise RuntimeError(f"generation discarded for {article_id} {kind} {key}")
    return text
