import os
import json
from typing import List, Dict
from statistics import mean

# ★ google-cloud-translate v2 임포트
from google.cloud import translate_v2 as translate  # pip install google-cloud-translate
import bert_score  # pip install bert-score

print("GOOGLE_APPLICATION_CREDENTIALS =", os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))

# ─── ROUGE Utilities ───────────────────────────────────────────────────────────

def tokenize(text: str) -> List[str]:
    return text.strip().split()

def get_ngrams(tokens: List[str], n: int) -> Dict[tuple, int]:
    counts = {}
    for i in range(len(tokens) - n + 1):
        gram = tuple(tokens[i : i + n])
        counts[gram] = counts.get(gram, 0) + 1
    return counts

def rouge_n(reference: str, candidate: str, n: int) -> float:
    ref_tokens  = tokenize(reference)
    cand_tokens = tokenize(candidate)

    ref_ngrams  = get_ngrams(ref_tokens, n)
    cand_ngrams = get_ngrams(cand_tokens, n)

    overlap = 0
    for gram, cnt in cand_ngrams.items():
        overlap += min(cnt, ref_ngrams.get(gram, 0))

    total_ref  = sum(ref_ngrams.values())
    total_cand = sum(cand_ngrams.values())

    recall    = overlap / total_ref  if total_ref  > 0 else 0.0
    precision = overlap / total_cand if total_cand > 0 else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)

def lcs_length(ref_tokens: List[str], cand_tokens: List[str]) -> int:
    m = len(ref_tokens)
    n = len(cand_tokens)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m - 1, -1, -1):
        for j in range(n - 1, -1, -1):
            if ref_tokens[i] == cand_tokens[j]:
                dp[i][j] = dp[i + 1][j + 1] + 1
            else:
                dp[i][j] = max(dp[i + 1][j], dp[i][j + 1])
    return dp[0][0]

def rouge_l(reference: str, candidate: str) -> float:
    ref_tokens  = tokenize(reference)
    cand_tokens = tokenize(candidate)
    lcs = lcs_length(ref_tokens, cand_tokens)

    recall    = lcs / len(ref_tokens)  if len(ref_tokens)  > 0 else 0.0
    precision = lcs / len(cand_tokens) if len(cand_tokens) > 0 else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


# ─── BERTScore Utility ─────────────────────────────────────────────────────────

# XLM-RoBERTa 계열을 멀티링구얼 평가용으로 사용
BERT_SCORE_MODEL = "xlm-roberta-base"

def compute_bertscore_f1(
    references: List[str],
    candidates: List[str],
    lang: str = "ko",
    model_type: str = BERT_SCORE_MODEL
) -> List[float]:
    """
    bert_score.score을 이용해 batch-wise로 F1 점수를 계산합니다.
    반환값은 각 쌍(reference, candidate)에 대한 F1 점수 리스트입니다.
    """
    P, R, F1 = bert_score.score(
        cands=candidates,
        refs=references,
        lang=lang,
        model_type=model_type,
        verbose=False,
    )
    return [float(x) for x in F1]


# ─── Google Translate Utility ──────────────────────────────────────────────────


def google_translate_batch(texts: List[str], target_lang: str = "ko") -> List[str]:
    """
    texts: 번역을 원하는 원문 리스트. 한 번에 최대 128개씩 묶어서 요청합니다.
    target_lang: 번역 대상 언어 ("ko"로 고정).
    반환: texts 순서대로 번역된 문자열 리스트.
    """
    # 1. 인증 방식은 이미 환경변수 GOOGLE_APPLICATION_CREDENTIALS로 설정되었다고 가정
    client = translate.Client()

    # 2. API 제한(한 번에 최대 128개) 대비해 texts를 슬라이싱해서 여러 번 호출
    MAX_CHUNK_SIZE = 128
    translated_all: List[str] = []

    # 3. 0~127, 128~255, ... 식으로 묶어서 요청
    for i in range(0, len(texts), MAX_CHUNK_SIZE):
        chunk = texts[i : i + MAX_CHUNK_SIZE]
        # 한 번에 chunk 길이만큼 번역 요청
        results = client.translate(chunk, target_language=target_lang, format_="text")
        # translate()가 반환하는 결과는 각 entry마다 {"translatedText": "..."} 딕셔너리 리스트
        translated_chunk = [entry["translatedText"].strip() for entry in results]
        translated_all.extend(translated_chunk)

    return translated_all


# ─── Load JSONL Files ────────────────────────────────────────────────────────────

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

    # 6) ROUGE 점수 계산
    def compute_avg_rouge(cands: List[str], refs: List[str]) -> Dict[str, float]:
        r1_list = [rouge_n(r, c, 1) for r, c in zip(refs, cands)]
        r2_list = [rouge_n(r, c, 2) for r, c in zip(refs, cands)]
        rl_list = [rouge_l(r, c)     for r, c in zip(refs, cands)]
        return {
            "ROUGE1": mean(r1_list) if r1_list else 0.0,
            "ROUGE2": mean(r2_list) if r2_list else 0.0,
            "ROUGEL": mean(rl_list)   if rl_list else 0.0,
        }

    rouge_google   = compute_avg_rouge(google_cands, references)
    rouge_baseline = compute_avg_rouge(baseline_cands, references)
    rouge_rag      = compute_avg_rouge(rag_cands, references)

    # 7) BERTScore 계산
    bert_google   = compute_bertscore_f1(references, google_cands, lang="ko")
    bert_baseline = compute_bertscore_f1(references, baseline_cands, lang="ko")
    bert_rag      = compute_bertscore_f1(references, rag_cands, lang="ko")

    avg_bert_google   = mean(bert_google)   if bert_google else 0.0
    avg_bert_baseline = mean(bert_baseline) if bert_baseline else 0.0
    avg_bert_rag      = mean(bert_rag)      if bert_rag else 0.0

    # 8) 결과 출력
    print("\n==== 평균 ROUGE F1 스코어 ====")
    print(f"Google 번역 평균")
    print(f"  ROUGE1 : {rouge_google['ROUGE1']:.4f}")
    print(f"  ROUGE2 : {rouge_google['ROUGE2']:.4f}")
    print(f"  ROUGEL : {rouge_google['ROUGEL']:.4f}\n")

    print(f"Baseline (파일번역) 평균")
    print(f"  ROUGE1 : {rouge_baseline['ROUGE1']:.4f}")
    print(f"  ROUGE2 : {rouge_baseline['ROUGE2']:.4f}")
    print(f"  ROUGEL : {rouge_baseline['ROUGEL']:.4f}\n")

    print(f"RAGあり 평균")
    print(f"  ROUGE1 : {rouge_rag['ROUGE1']:.4f}")
    print(f"  ROUGE2 : {rouge_rag['ROUGE2']:.4f}")
    print(f"  ROUGEL : {rouge_rag['ROUGEL']:.4f}\n")

    print("==== 평균 BERTScore F1 ====")
    print(f"Google 번역 평균 BERTScore F1   : {avg_bert_google:.4f}")
    print(f"Baseline 평균 BERTScore F1       : {avg_bert_baseline:.4f}")
    print(f"RAGあり 평균 BERTScore F1        : {avg_bert_rag:.4f}")

    # 9) 개별 점수 JSONL로 저장
    with open(os.path.join(BASE_DIR, "eval_google.jsonl"), "w", encoding="utf-8") as fw_g, \
         open(os.path.join(BASE_DIR, "eval_baseline.jsonl"), "w", encoding="utf-8") as fw_b, \
         open(os.path.join(BASE_DIR, "eval_rag.jsonl"), "w", encoding="utf-8") as fw_r:

        for idx, src in enumerate(sources_list):
            entry_google = {
                "source": src,
                "reference": ref_map[src],
                "translation": google_cands[idx],
                "rouge1": rouge_n(ref_map[src], google_cands[idx], 1),
                "rouge2": rouge_n(ref_map[src], google_cands[idx], 2),
                "rougel": rouge_l(ref_map[src], google_cands[idx]),
                "bertscore_f1": bert_google[idx]
            }
            fw_g.write(json.dumps(entry_google, ensure_ascii=False) + "\n")

            entry_baseline = {
                "source": src,
                "reference": ref_map[src],
                "translation": baseline_map[src],
                "rouge1": rouge_n(ref_map[src], baseline_map[src], 1),
                "rouge2": rouge_n(ref_map[src], baseline_map[src], 2),
                "rougel": rouge_l(ref_map[src], baseline_map[src]),
                "bertscore_f1": bert_baseline[idx]
            }
            fw_b.write(json.dumps(entry_baseline, ensure_ascii=False) + "\n")

            entry_rag = {
                "source": src,
                "reference": ref_map[src],
                "translation": rag_map[src],
                "rouge1": rouge_n(ref_map[src], rag_map[src], 1),
                "rouge2": rouge_n(ref_map[src], rag_map[src], 2),
                "rougel": rouge_l(ref_map[src], rag_map[src]),
                "bertscore_f1": bert_rag[idx]
            }
            fw_r.write(json.dumps(entry_rag, ensure_ascii=False) + "\n")

    print("\n개별 평가 결과를 eval_google.jsonl, eval_baseline.jsonl, eval_rag.jsonl에 저장했습니다.")