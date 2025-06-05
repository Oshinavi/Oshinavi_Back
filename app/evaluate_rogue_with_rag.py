import json
import os
import time
from typing import List, Dict
from statistics import mean

# ■■ 以下、あらかじめインストール・構成済みのパッケージを想定 ──────────
#   pip install sentence-transformers faiss-cpu fugashi rank_bm25 langchain-anthropic langchain
#   または ChatOpenAI 用に langchain-chat_models, openai パッケージ など
# ───────────────────────────────────────────────────────────────

from fugashi import Tagger
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
import faiss

from langchain_anthropic import ChatAnthropic
from langchain.chat_models import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain

# ────────────────────────────────────────────────────────────────────────────────
#  ➤ BASE_DIR: 이 파일이 있는 디렉터리(= app/) 경로
BASE_DIR = os.path.dirname(__file__)

# ➤ .env 파일 위치 (app/config/settings.env)
ENV_PATH = os.path.join(BASE_DIR, "config", "settings.env")

# ➤ settings.env 에 적혀 있는 KEY=VALUE 형식의 환경변수를 읽어서 os.environ에 설정
if os.path.exists(ENV_PATH):
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            # 빈 줄 혹은 주석(#)이면 건너뛰기
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()
# ────────────────────────────────────────────────────────────────────────────────

class PromptType(str):
    TRANSLATE = "translate"
    # （必要に応じて他もあるが今回は翻訳のみ使う）


SYSTEM_PROMPTS: Dict[PromptType, str] = {
    PromptType.TRANSLATE: """
You are an AI translator. Your task is to translate Twitter's Japanese text into natural, cute Korean, while preserving specific elements.

Follow these instructions precisely:
1.  Preserve the following elements EXACTLY as they appear in the original text (do NOT translate or alter them):
    * Hashtags (tokens starting with #)
    * Mentions (tokens starting with @)
    * The literal prefix "RT @user:" (including the space)
    * Emojis (emojis like 😂, ✨, ❤️, etc.)

2.  Translate ALL other Japanese characters and words into natural, cute Korean.
    * Pay close attention to adverbs and nuanced expressions (e.g., 「果たして」, 「やっぱり」, 「まさか」) and translate them naturally, reflecting their nuance and emotional tone within the context.
    * Do not skip seemingly minor words or fillers; translate everything necessary for natural flow.
    * Use contextual paraphrasing to ensure the translated Korean is smooth, natural, and captures the original meaning accurately, rather than just a literal word-for-word translation.

3.  Output ONLY the final translated Korean text. Do not include the original text, explanations, or any other information.
""".strip(),
}

def get_few_shot_examples(pt: PromptType) -> str:
    """
    実運用では few_shot.json から読み込むが、ここでは省略して空文字を返す。
    """
    return ""

def _build_system_prompt(prompt_type: PromptType, **kwargs) -> str:
    few = get_few_shot_examples(prompt_type)
    base = SYSTEM_PROMPTS[prompt_type].strip()
    if kwargs:
        base = base.format(**kwargs)
    return f"{few}\n\n{base}"

class DummyRAGService:
    """
    RAGなし（翻訳チェーンに渡すと get_context が常に空リストを返す）
    """
    def get_context(self, query: str) -> List[str]:
        return []

class RAGService:
    """
    FAISS + BM25 を組み合わせた RAGService 実装
    （インデックスファイル、メタデータファイルをあらかじめ作っておくこと）
    """
    def __init__(
        self,
        index_path: str,
        meta_path: str,
        top_k: int = 15,
        lexical_weight: float = 0.7,
    ):
        # 1) FAISS インデックスをロード
        self.index = faiss.read_index(index_path)

        # 2) メタデータ(JSON)をロード
        with open(meta_path, encoding="utf-8") as f:
            self.metadata: List[Dict[str, str]] = json.load(f)
        self.source_texts = [entry["text"] for entry in self.metadata]

        # 3) Embedding モデルを初期化
        self.embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

        # 4) 形態素解析器を初期化
        self.tagger = Tagger()

        # 5) BM25 インデックスを構築
        tokenized_corpus = [self._tokenize(text) for text in self.source_texts]
        self.bm25 = BM25Okapi(tokenized_corpus)

        self.top_k = top_k
        self.lexical_weight = lexical_weight

    def _tokenize(self, text: str) -> List[str]:
        """
        日本語を形態素単位でトークナイズ
        """
        return [word.surface for word in self.tagger(text)]

    def get_context(self, query: str) -> List[str]:
        """
        クエリに対して FAISS + BM25 を組み合わせて上位 top_k の "原文 → 翻訳" を返す
        """
        # 1) Semantic 検索 (L2正規化済み so Cosine)
        query_embedding = self.embedder.encode([query])
        sims, indices = self.index.search(query_embedding, self.top_k)
        sims = sims[0]
        semantic_indices = [int(i) for i in indices[0] if 0 <= i < len(self.source_texts)]

        # 2) Lexical 検索 (BM25)
        tokenized_query = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(tokenized_query)
        top_lex_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[: self.top_k]

        # 3) 候補 indices の union
        candidate_indices = set(semantic_indices) | set(top_lex_indices)

        # 4) Semantic similarity 正規化
        max_sim = float(sims.max()) if sims.size > 0 else 1.0
        sem_score_map = {semantic_indices[i]: sims[i] / max_sim for i in range(len(semantic_indices))}

        # 5) BM25 正規化
        max_bm = float(bm25_scores.max()) if bm25_scores.size > 0 else 1.0

        # 6) Combined スコア計算
        combined_scores: List[(int, float)] = []
        for idx in candidate_indices:
            sem_sc = sem_score_map.get(idx, 0.0)
            lex_sc = (bm25_scores[idx] / max_bm) if max_bm > 0 else 0.0
            total_sc = sem_sc + self.lexical_weight * lex_sc
            combined_scores.append((idx, total_sc))

        # 7) 上位 top_k を選択
        combined_scores.sort(key=lambda x: x[1], reverse=True)
        selected = [idx for idx, _ in combined_scores[: self.top_k]]

        # 8) “原文 → 翻訳” フォーマットで返却
        return [f"{self.metadata[i]['text']} → {self.metadata[i]['translation']}" for i in selected]

class TranslationChain:
    """
    “Baseline” と “RAG” 両方で使う共通の翻訳チェーン。
    RAGなしの場合は DummyRAGService を渡すだけで、contexts が空になり、
    実質的には“ただの Claude 翻訳”と同等の挙動になる。
    """
    def __init__(self, rag_service, model_name: str = "claude-3-7-sonnet-20250219"):
        self.rag = rag_service

        # ▶ ChatAnthropic 사용 시, 이미 os.environ["ANTHROPIC_API_KEY"] 를 읽어왔으므로
        #    별도로 전달하지 않아도 내부에서 해당 환경변수를 사용하게 됩니다.
        self.llm = ChatAnthropic(
            model_name=model_name,
            timeout=120,
            temperature=0.3,
            stop=["\n\nHuman:"],
        )

        prompt = PromptTemplate(
            input_variables=["system", "contexts", "text"],
            template="""
<|system|>
{system}

### Reference dictionary:
{contexts}

<|user|>
{text}
""".strip(),
        )
        self.chain = LLMChain(llm=self.llm, prompt=prompt, output_key="translation")

    def run(self, text: str, timestamp: str) -> str:
        # “翻訳”専用のシステムプロンプト
        system = _build_system_prompt(PromptType.TRANSLATE)
        contexts = self._build_contexts(text)
        return self.chain.predict(system=system, contexts=contexts, text=text)

    def _build_contexts(self, text: str) -> str:
        """
        RAGService から得られたコンテキストを “- 〜” のリスト形式にして返す
        """
        contexts = self.rag.get_context(text)
        if not contexts:
            return ""
        return "\n".join(f"- {c}" for c in contexts)

# ■■ ROUGE スコア計算ユーティリティ ──────────────────────────────────

def tokenize(text: str) -> List[str]:
    """
    非日本語専用の非常にシンプルなトークナイザー。
    韓国語・英語は空白区切りで十分。日本語はここでは使わないので無視。
    """
    return text.strip().split()

def get_ngrams(tokens: List[str], n: int) -> Dict[tuple, int]:
    counts = {}
    for i in range(len(tokens) - n + 1):
        gram = tuple(tokens[i : i + n])
        counts[gram] = counts.get(gram, 0) + 1
    return counts

def rouge_n(reference: str, candidate: str, n: int) -> Dict[str, float]:
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
    f1        = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {"precision": precision, "recall": recall, "f1": f1}

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

def rouge_l(reference: str, candidate: str) -> Dict[str, float]:
    ref_tokens  = tokenize(reference)
    cand_tokens = tokenize(candidate)
    lcs = lcs_length(ref_tokens, cand_tokens)

    recall    = lcs / len(ref_tokens)  if len(ref_tokens)  > 0 else 0.0
    precision = lcs / len(cand_tokens) if len(cand_tokens) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {"precision": precision, "recall": recall, "f1": f1}

# ■■ メイン処理 ────────────────────────────────────────────────────────

def load_dataset(jsonl_path: str) -> List[Dict[str, str]]:
    """
    JSONL ファイルを読み込み、
    各行に {'source': ..., 'reference': ...} がある想定。
    """
    data = []
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            obj = json.loads(line)
            # 必要最低限のキーが存在するかチェック
            if 'source' not in obj or 'reference' not in obj:
                raise ValueError("각 행에 'source' 와 'reference' 키가 필요합니다.")
            data.append(obj)
    return data

def compute_rouge_scores(
    items: List[Dict[str, str]],
    baseline_chain: TranslationChain,
    rag_chain: TranslationChain,
    timestamp: str = None
) -> Dict[str, Dict[str, float]]:
    """
    items: List[{'source': JapaneseOriginal, 'reference': CorrectKorean}]
    baseline_chain: DummyRAG を使った翻訳チェーン
    rag_chain: RAGService を使った翻訳チェーン
    timestamp: ScheduleChain 用のタイムスタンプだが、翻訳には不要なので None を渡せば OK
    """
    scores = {
        'baseline': {'rouge1': [], 'rouge2': [], 'rougeL': []},
        'rag':      {'rouge1': [], 'rouge2': [], 'rougeL': []}
    }

    for idx, item in enumerate(items, 1):
        src = item['source']
        ref = item['reference']

        # 1) Baseline 翻訳（RAGなし）
        try:
            baseline_out = baseline_chain.run(src, timestamp or "")
        except Exception as e:
            print(f"[Warning] Baseline 翻訳でエラー at {idx}: {e}")
            baseline_out = ""

        # 2) RAGあり 翻訳
        try:
            rag_out = rag_chain.run(src, timestamp or "")
        except Exception as e:
            print(f"[Warning] RAG 翻訳でエラー at {idx}: {e}")
            rag_out = ""

        # 3) ROUGE-1,2,L 計算
        r1_base = rouge_n(ref, baseline_out, 1)['f1']
        r1_rag  = rouge_n(ref, rag_out, 1)['f1']

        r2_base = rouge_n(ref, baseline_out, 2)['f1']
        r2_rag  = rouge_n(ref, rag_out, 2)['f1']

        rl_base = rouge_l(ref, baseline_out)['f1']
        rl_rag  = rouge_l(ref, rag_out)['f1']

        scores['baseline']['rouge1'].append(r1_base)
        scores['baseline']['rouge2'].append(r2_base)
        scores['baseline']['rougeL'].append(rl_base)

        scores['rag']['rouge1'].append(r1_rag)
        scores['rag']['rouge2'].append(r2_rag)
        scores['rag']['rougeL'].append(rl_rag)

        # デバッグ用ログ（必要に応じてコメントアウト可）
        print(f"[{idx}/{len(items)}] Source: {src}")
        print(f"  Baseline → {baseline_out}")
        print(f"  RAG      → {rag_out}")
        print(f"  REF      → {ref}")
        print(f"  ▶ ROUGE1_base: {r1_base:.4f}, ROUGE1_rag: {r1_rag:.4f}")
        print(f"  ▶ ROUGE2_base: {r2_base:.4f}, ROUGE2_rag: {r2_rag:.4f}")
        print(f"  ▶ ROUGEL_base: {rl_base:.4f}, ROUGEL_rag: {rl_rag:.4f}")
        print("───────────────────────────────────────────────")

    # 全文例を集計して平均値を計算
    avg = {
        'baseline': {key: mean(vals) if vals else 0.0 for key, vals in scores['baseline'].items()},
        'rag':      {key: mean(vals) if vals else 0.0 for key, vals in scores['rag'].items()}
    }
    return avg

if __name__ == "__main__":
    # ─────────── 設定部分 ───────────
    # 1) JSONL ファイルパス
    JSONL_PATH = os.path.join(BASE_DIR, "translations.jsonl")

    # 2) RAG 用に事前に構築した FAISS index と metadata JSON のパス
    INDEX_PATH = os.path.join(BASE_DIR, "rag_data", "vector_store", "faiss_index.bin")
    META_PATH  = os.path.join(BASE_DIR, "rag_data", "vector_store", "metadata.json")

    # 3) 使用するモデル名（必要に応じて書き換え）
    CLAUDE_MODEL = "claude-3-7-sonnet-20250219"
    # もし OpenAI の ChatGPT で回したい場合は以下のように:
    # CLAUDE_MODEL = None
    #  その場合、TranslationChain の llm を ChatOpenAI(... ) に書き換える必要があります。

    # ─────────── RAGService と 各翻訳チェーン の初期化 ───────────
    # 「Baseline」(DummyRAG) 用チェーン
    dummy_rag = DummyRAGService()
    baseline_chain = TranslationChain(rag_service=dummy_rag, model_name=CLAUDE_MODEL)

    # 「RAGあり」用チェーン
    rag_service = RAGService(
        index_path=INDEX_PATH,
        meta_path=META_PATH,
        top_k=15,
        lexical_weight=0.7
    )
    rag_chain = TranslationChain(rag_service=rag_service, model_name=CLAUDE_MODEL)

    # ─────────── データロード ───────────
    dataset = load_dataset(JSONL_PATH)

    # ─────────── 번역 결과 저장용 리스트 초기화 ───────────
    baseline_outputs: List[Dict[str, str]] = []
    rag_outputs: List[Dict[str, str]] = []

    # ─────────── DUMMY RAG 과 RAG 적용 번역 및 저장 ───────────
    for idx, item in enumerate(dataset, 1):
        src = item['source']
        # Baseline 번역
        try:
            baseline_out = baseline_chain.run(src, "")
        except Exception as e:
            print(f"[Warning] Baseline 번역 에러 at {idx}: {e}")
            baseline_out = ""
        # RAG 적용 번역
        try:
            rag_out = rag_chain.run(src, "")
        except Exception as e:
            print(f"[Warning] RAG 번역 에러 at {idx}: {e}")
            rag_out = ""

        # 결과를 리스트에 저장
        baseline_outputs.append({"source": src, "translation": baseline_out})
        rag_outputs.append({"source": src, "translation": rag_out})

    # ─────────── 번역 결과를 JSONL 파일로 쓰기 ───────────
    baseline_jsonl_path = os.path.join(BASE_DIR, "baseline_translations.jsonl")
    rag_jsonl_path      = os.path.join(BASE_DIR, "rag_translations.jsonl")

    with open(baseline_jsonl_path, "w", encoding="utf-8") as fw_baseline:
        for rec in baseline_outputs:
            fw_baseline.write(json.dumps(rec, ensure_ascii=False) + "\n")

    with open(rag_jsonl_path, "w", encoding="utf-8") as fw_rag:
        for rec in rag_outputs:
            fw_rag.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ─────────── ROUGE 평가 실행 ───────────
    avg_scores = compute_rouge_scores(dataset, baseline_chain, rag_chain, timestamp="")

    print("\n==== 평균 ROUGE F1 스코어 (최종 결과) ====")
    print("Baseline (RAGなし) 평균")
    for k, v in avg_scores['baseline'].items():
        print(f"  {k.upper():>7}: {v:.4f}")

    print("\nRAGあり 평균")
    for k, v in avg_scores['rag'].items():
        print(f"  {k.upper():>7}: {v:.4f}")

    print(f"\n▶ Baseline 번역 결과: {baseline_jsonl_path}")
    print(f"▶ RAG 번역 결과:      {rag_jsonl_path}")