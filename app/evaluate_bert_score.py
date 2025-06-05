import json
import os
from typing import List, Dict
from statistics import mean

import bert_score  # pip install bert-score

# ──── 설정 부분 ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)

# 원본 reference가 있는 JSONL (source, reference)
REF_JSONL = os.path.join(BASE_DIR, "translations.jsonl")

# 각 번역 결과가 담긴 JSONL (source, translation)
BASELINE_JSONL = os.path.join(BASE_DIR, "baseline_translations.jsonl")
RAG_JSONL      = os.path.join(BASE_DIR, "rag_translations.jsonl")

# BERTScore에 사용할 모델 (한국어 평가용)
BERT_SCORE_MODEL = "xlm-roberta-base"

# ──── 파일 로드 유틸리티 ─────────────────────────────────────────────────────────

def load_reference(path: str) -> Dict[str, str]:
    """
    translations.jsonl에서 각 source → reference 맵을 반환
    { source_text: reference_korean, ... }
    """
    ref_map = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            src = obj["source"].strip()
            ref = obj["reference"].strip()
            ref_map[src] = ref
    return ref_map

def load_translations(path: str) -> Dict[str, str]:
    """
    baseline_translations.jsonl 혹은 rag_translations.jsonl에서
    { source_text: translation_text, ... } 맵을 반환
    `"translation"` 키를 사용합니다.
    """
    trans_map = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            src = obj["source"].strip()
            trans = obj["translation"].strip()
            trans_map[src] = trans
    return trans_map

# ──── BERTScore 계산 함수 ────────────────────────────────────────────────────

def compute_bertscore_f1(
    references: List[str],
    candidates: List[str],
    lang: str = "ko",
    model_type: str = BERT_SCORE_MODEL
) -> List[float]:
    """
    bert_score.score을 이용해 batch-wise로 F1 점수를 계산합니다.
    반환값은 각 쌍(reference, candidate)에 대한 F1 리스트입니다.
    """
    P, R, F1 = bert_score.score(
        candidates,      # candidate 문장 리스트
        references,      # reference 문장 리스트
        lang=lang,
        model_type=model_type,
        verbose=False,
    )
    # torch.Tensor → Python float 리스트
    return [float(x) for x in F1]

# ──── 메인 처리 ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 1) reference 맵 로드
    ref_map = load_reference(REF_JSONL)

    # 2) 각 번역 결과 맵 로드 (baseline/ rag 모두 "translation" 키 사용)
    baseline_map = load_translations(BASELINE_JSONL)
    rag_map      = load_translations(RAG_JSONL)

    # 3) source 키가 세 파일에 공통으로 존재하는지 확인
    common_sources = set(ref_map.keys()) & set(baseline_map.keys()) & set(rag_map.keys())
    if not common_sources:
        raise RuntimeError("source가 세 파일에 공통으로 존재하지 않습니다.")

    # 4) 정렬된 source 리스트 생성 (계산 일관성을 위해)
    sources_sorted = sorted(common_sources)

    # 5) reference / baseline / rag 번역 리스트 생성
    references      = [ref_map[src] for src in sources_sorted]
    baseline_cands  = [baseline_map[src] for src in sources_sorted]
    rag_cands       = [rag_map[src]      for src in sources_sorted]

    # 6) BERTScore(F1) 일괄 계산
    baseline_f1_scores = compute_bertscore_f1(references, baseline_cands, lang="ko")
    rag_f1_scores      = compute_bertscore_f1(references, rag_cands,      lang="ko")

    # 7) 평균값 산출
    avg_baseline_bertscore = mean(baseline_f1_scores) if baseline_f1_scores else 0.0
    avg_rag_bertscore      = mean(rag_f1_scores)      if rag_f1_scores else 0.0

    # 8) 결과 출력
    print("==== BERTScore F1 (최종 결과) ====")
    print(f"Baseline (RAGなし) 평균 BERTScore F1: {avg_baseline_bertscore:.4f}")
    print(f"RAGあり 평균 BERTScore F1: {avg_rag_bertscore:.4f}")

    # 9) 개별 점수도 JSONL으로 저장
    baseline_out_path = os.path.join(BASE_DIR, "bertscore_baseline.jsonl")
    rag_out_path      = os.path.join(BASE_DIR, "bertscore_rag.jsonl")

    with open(baseline_out_path, "w", encoding="utf-8") as fw_base, \
         open(rag_out_path,      "w", encoding="utf-8") as fw_rag:
        for idx, src in enumerate(sources_sorted):
            entry_base = {
                "source": src,
                "reference": ref_map[src],
                "translation": baseline_map[src],
                "bertscore_f1": baseline_f1_scores[idx]
            }
            fw_base.write(json.dumps(entry_base, ensure_ascii=False) + "\n")

            entry_rag = {
                "source": src,
                "reference": ref_map[src],
                "translation": rag_map[src],
                "bertscore_f1": rag_f1_scores[idx]
            }
            fw_rag.write(json.dumps(entry_rag, ensure_ascii=False) + "\n")

    print(f"\n개별 BERTScore 결과를 '{baseline_out_path}' 와 '{rag_out_path}' 에 저장했습니다.")