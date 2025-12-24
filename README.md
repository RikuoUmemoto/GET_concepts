
# Ollama 概念抽出スクリプト

ローカルの Ollama (`elyza:8b-q8`) を使って、

- `syllabus_2025_cut_sotsuken.jsonl` に入っている各授業の `text`
- から
  - `raw_teaches`（その授業で学ぶ概念候補）
  - `raw_requires`（その授業の前提となる概念候補）

を抽出して `raw_concepts_output.jsonl` に出力するスクリプトです。

## 前提

- Ollama がローカルで動いていること
- `elyza:8b-q8` モデルが pull 済みであること

```bash
ollama pull elyza:8b-q8
```

## 使い方

1. この ZIP を解凍する
2. 同じディレクトリに `syllabus_2025_cut_sotsuken.jsonl` を置く
3. ターミナルで以下を実行

```bash
cd ollama_concept_extractor
python3 extract_raw_concepts.py
```

4. 正常終了すると、`raw_concepts_output.jsonl` が生成されます。

## 入力フォーマット

`syllabus_2025_cut_sotsuken.jsonl` は 1行1 JSON で、少なくとも次のキーを含むことを想定しています。

```json
{
  "course_code": "H4020",
  "title": "C++ プログラミング",
  "text": "シラバス本文..."
}
```

## 出力フォーマット

`raw_concepts_output.jsonl` も 1行1 JSON で、スキーマは以下の通りです。

```json
{
  "course_code": "H4020",
  "title": "C++ プログラミング",
  "raw_teaches": [
    "オブジェクト指向プログラミング",
    "クラスとコンストラクタ",
    "..."
  ],
  "raw_requires": [
    "C言語の基本構文",
    "配列とポインタの理解",
    "..."
  ],
  "llm_notes": [
    "補足や曖昧さなど、LLM側のメモ（なければ空配列）"
  ]
}
```

この `raw_teaches` / `raw_requires` を全授業分集めたものが、
後続の「概念ノードの正規化」「DAG エッジ構築」の材料になります。
