import os
import json
from typing import List, Dict
from statistics import mean

# Google Cloud Translation v2
from google.cloud import translate_v2 as translate  # pip install google-cloud-translate
import sacrebleu  # pip install sacrebleu

print("GOOGLE_APPLICATION_CREDENTIALS =", os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))

# ─── 파일 로드 유틸리티 ─────────────────────────────────────────────────────────

def load_reference_map(path: str) -> Dict[str, str]:
    """
    translations.jsonl에서 {source: reference} 맵을 반환
    """
    ref_map = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            src = obj["source"].strip()
            ref = obj["reference"].strip()
            ref_map[src] = ref
    return ref_map

def load_translation_map(path: str) -> Dict[str, str]:
    """
    baseline_translations.jsonl 또는 rag_translations.jsonl에서
    {source: translation} 맵을 반환
    """
    trans_map = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            src = obj["source"].strip()
            trans = obj["translation"].strip()
            trans_map[src] = trans
    return trans_map

# ─── BLEU 계산 함수 ────────────────────────────────────────────────────────────

def compute_sentence_bleu(reference: str, candidate: str) -> float:
    """
    sacrebleu.sentence_bleu을 이용해 단일 문장 BLEU 점수를 계산합니다.
    반환값은 0~100 범위의 BLEU 점수입니다.
    """
    return sacrebleu.sentence_bleu(candidate, [reference]).score

# ─── Google 번역 유틸리티 ────────────────────────────────────────────────────

def google_translate_batch(texts: List[str], target_lang: str = "ko") -> List[str]:
    """
    texts: 번역할 원문 리스트. 최대 128개씩 묶어서 요청합니다.
    target_lang: 번역 대상 언어 ("ko"로 고정).
    반환: texts 순서대로 번역된 문자열 리스트.
    """
    client = translate.Client()
    MAX_CHUNK_SIZE = 128
    translated_all: List[str] = []

    for i in range(0, len(texts), MAX_CHUNK_SIZE):
        chunk = texts[i : i + MAX_CHUNK_SIZE]
        results = client.translate(chunk, target_language=target_lang, format_="text")
        translated_chunk = [entry["translatedText"].strip() for entry in results]
        translated_all.extend(translated_chunk)

    return translated_all

# ─── Main 평가 스크립트 ────────────────────────────────────────────────────────

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(__file__)

    # 1) 파일 경로 설정
    REF_JSONL      = os.path.join(BASE_DIR, "translations.jsonl")
    BASELINE_JSONL = os.path.join(BASE_DIR, "baseline_translations.jsonl")
    RAG_JSONL      = os.path.join(BASE_DIR, "rag_translations.jsonl")

    # 2) 맵 로드
    ref_map       = load_reference_map(REF_JSONL)
    baseline_map  = load_translation_map(BASELINE_JSONL)
    rag_map       = load_translation_map(RAG_JSONL)

    # 3) 공통된 source 키만 추출
    common_sources = sorted(set(ref_map.keys()) & set(baseline_map.keys()) & set(rag_map.keys()))
    if not common_sources:
        raise RuntimeError("source가 세 파일에 공통으로 존재하지 않습니다.")

    # 4) reference / baseline / rag 번역 리스트 생성
    references     = [ref_map[src] for src in common_sources]
    baseline_cands = [baseline_map[src] for src in common_sources]
    rag_cands      = [rag_map[src]      for src in common_sources]
    sources_list   = common_sources

    # 5) Google 번역 (batch)
    google_cands = google_translate_batch(sources_list, target_lang="ko")

    # 6) BLEU 점수 계산
    baseline_bleu_scores = []
    rag_bleu_scores      = []
    google_bleu_scores   = []

    for idx, src in enumerate(sources_list):
        ref = references[idx]
        base_cand = baseline_cands[idx]
        rag_cand  = rag_cands[idx]
        goog_cand = google_cands[idx]

        baseline_bleu = compute_sentence_bleu(ref, base_cand)
        rag_bleu      = compute_sentence_bleu(ref, rag_cand)
        google_bleu   = compute_sentence_bleu(ref, goog_cand)

        baseline_bleu_scores.append(baseline_bleu)
        rag_bleu_scores.append(rag_bleu)
        google_bleu_scores.append(google_bleu)

    # 7) 평균값 산출
    avg_baseline_bleu = mean(baseline_bleu_scores) if baseline_bleu_scores else 0.0
    avg_rag_bleu      = mean(rag_bleu_scores)      if rag_bleu_scores      else 0.0
    avg_google_bleu   = mean(google_bleu_scores)   if google_bleu_scores   else 0.0

    # 8) 결과 출력
    print("\n==== Sentence-BLEU (최종 결과) ====")
    print(f"Google 번역 평균 BLEU   : {avg_google_bleu:.2f}")
    print(f"Baseline 평균 BLEU       : {avg_baseline_bleu:.2f}")
    print(f"RAGあり 평균 BLEU        : {avg_rag_bleu:.2f}")

    # 9) 개별 점수 JSONL로 저장
    google_out_path   = os.path.join(BASE_DIR, "bleu_google.jsonl")
    baseline_out_path = os.path.join(BASE_DIR, "bleu_baseline.jsonl")
    rag_out_path      = os.path.join(BASE_DIR, "bleu_rag.jsonl")

    with open(google_out_path,   "w", encoding="utf-8") as fw_g, \
         open(baseline_out_path, "w", encoding="utf-8") as fw_b, \
         open(rag_out_path,      "w", encoding="utf-8") as fw_r:

        for idx, src in enumerate(sources_list):
            entry_google = {
                "source": src,
                "reference": ref_map[src],
                "translation": google_cands[idx],
                "bleu": google_bleu_scores[idx]
            }
            fw_g.write(json.dumps(entry_google, ensure_ascii=False) + "\n")

            entry_baseline = {
                "source": src,
                "reference": ref_map[src],
                "translation": baseline_map[src],
                "bleu": baseline_bleu_scores[idx]
            }
            fw_b.write(json.dumps(entry_baseline, ensure_ascii=False) + "\n")

            entry_rag = {
                "source": src,
                "reference": ref_map[src],
                "translation": rag_map[src],
                "bleu": rag_bleu_scores[idx]
            }
            fw_r.write(json.dumps(entry_rag, ensure_ascii=False) + "\n")

    print(f"\n개별 BLEU 결과를 '{google_out_path}', '{baseline_out_path}', '{rag_out_path}'에 저장했습니다.")