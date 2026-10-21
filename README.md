# CRYSTAL

진위(veracity) 기반 설명형 뉴스 추천 데모. PRISM(CIKM'26 demo)의 정치 성향 축을 가짜뉴스 진위로 바꾼 것.

- 진위 판정: 구글 Fact Check Tools API + RoBERTa 10-fold 교차 예측 (out-of-fold, temperature scaling)
- 판정 근거 키워드: Integrated Gradients + spaCy 구문 확장
- 같은 사건 매칭: SBERT(all-MiniLM-L6-v2) + HDBSCAN, 군집 내 코사인 ≥ 0.7
- 추천: CROWN (crown-www25)
- 설명 문장: Gemini (verbalizer 역할만)

## 실행

데이터 파일(`crystal/data/*.jsonl`)과 가중치는 저장소에 없음. 파이프라인 산출물을 받아 넣은 뒤:

```
set GEMINI_API_KEY=...   # 또는 .env
python -X utf8 -m uvicorn crystal.web.app:app --port 8765
```

## Docker

```
docker build -t crystal .
docker run -p 8765:8765 -e GEMINI_API_KEY=... crystal
```
