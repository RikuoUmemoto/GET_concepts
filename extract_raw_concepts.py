#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
syllabus_2025_cut_sotsuken.jsonl を読み込み、
各行の text をローカルの Ollama (llama3.1:8b) に投げて
「概念だけ」抽出するスクリプト。

★ course_code と title は LLM に触らせず、
   入力JSONLからそのままコピーする。
★ LLM には JSON を書かせず、
   [TEACHES]/[REQUIRES]/[NOTES] 形式のプレーンテキストだけ書かせる。
★ Python側でパースして JSON にするので、出力JSONは絶対に壊れない。

使い方:
  1. このファイルと同じディレクトリに
     syllabus_2025_cut_sotsuken.jsonl を置く
  2. ターミナルで:
       python3 extract_raw_concepts.py
  3. 出力: raw_concepts_output.jsonl
"""

import json
import time
import requests
import re

#INPUT_JSONL = "syllabus_2025_cut_sotsuken.jsonl"
#OUTPUT_JSONL = "raw_concepts_output.jsonl"

#INPUT_JSONL = "lang.jsonl"
#OUTPUT_JSONL = "lang_output.jsonl"

#INPUT_JSONL = "theory.jsonl"
#OUTPUT_JSONL = "theory_output.jsonl"

INPUT_JSONL = "technology.jsonl"
OUTPUT_JSONL = "technology_output.jsonl"

#INPUT_JSONL = "test1.jsonl"
#OUTPUT_JSONL = "test1_output.jsonl"

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
#MODEL = "llama3.1:8b"
MODEL = "qwen2.5:7b"
MAX_RETRY = 3
SLEEP_SEC = 1.0  # 負荷軽減用

TEACH_MAX = 5
REQ_MAX = 5

SYSTEM_PROMPT = r"""
あなたは大学カリキュラム分析の専門家です。
与えられたシラバスのテキストから、
(1) 授業で扱う概念（Teaches）
(2) 履修に必要な前提知識（Requires）
のみを日本語を用いて箇条書きで抽出してください。

必ず次のテキスト形式「のみ」を出力してください。余計な説明文は一切書かないこと。

[TEACHES]
- （この授業で新たに学ぶ重要な概念・知識・スキルの候補を重要度の高い順に最大5個）

[REQUIRES]
- （この授業を受ける前に知っていることが望ましい概念・知識・スキルの候補を最大5個）


制約:
- [TEACHES]は「授業概要・到達目標・授業計画」からこの科目の中心となる基礎概念上位5個を抽出する。

- 科目名・授業名に含まれる重要な専門用語はこの授業の中核概念とみなし、必ず [TEACHES] の最上位に含めること。

- [REQUIRES]は「履修条件・前提知識・この授業を受けるために必要な事項」などの記述に基づいて抽出すること。
  → 履修条件や前提知識に関する記述がほとんど無い場合、[REQUIRES] は空欄でもよい
  → 授業で扱う内容（TEACHESに入るべき概念）を、前提知識として推測してはいけない。

- 5〜30 文字程度の「名詞句」とし、「〜すること」「〜ができるようになる」などの文章や目標文は避ける。

- 「意欲」「態度」「レポート提出」「授業に参加すること」などの行動・態度・運用ルールは含めない。

- 教員名・曜日・教室など「学ぶ概念ではない情報」は含めない。

- [REQUIRES]に含めてよいのは、授業開始前に既に知っていることが期待されている内容だけとする。

"""

USER_PROMPT_TEMPLATE = """
以下は1つの授業のシラバス情報です。
この授業について、[TEACHES] / [REQUIRES] 形式で出力してください。

======== シラバス情報 ========
{SYLLABUS_TEXT}
==============================
"""


def call_ollama_plain(syllabus_text: str) -> str:
    """LLM にプレーンテキスト形式で [TEACHES]/[REQUIRES]/[NOTES] を書かせる。"""
    user_prompt = USER_PROMPT_TEMPLATE.format(SYLLABUS_TEXT=syllabus_text)

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        # JSONモードは使わない（壊れやすいため）
        "stream": False,
        "options": {
            "num_ctx": 32768,
            "temperature": 0
        },
    }

    for attempt in range(1, MAX_RETRY + 1):
        try:
            r = requests.post(OLLAMA_URL, json=payload, timeout=300)
            r.raise_for_status()
            data = r.json()
            content = data.get("message", {}).get("content", "")
            return content
        except Exception as e:
            print(f"[ERROR] call_ollama_plain failed (attempt {attempt}/{MAX_RETRY}): {e}")
            time.sleep(SLEEP_SEC)

    return ""  # 失敗時は空文字


def parse_sections(text: str):
    """
    LLM の出力テキストから [TEACHES]/[REQUIRES]/[NOTES] をパースして
    dict にして返す。
    """
    teaches = []
    requires = []
    notes = []

    current = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        upper = line.upper()
        if upper.startswith("[TEACHES]"):
            current = "teaches"
            continue
        if upper.startswith("[REQUIRES]"):
            current = "requires"
            continue
        if upper.startswith("[NOTES]"):
            current = "notes"
            continue

        if line.startswith(("-", "・")):
            item = line.lstrip("・-").strip()
            if not item:
                continue
            if current == "teaches":
                teaches.append(item)
            elif current == "requires":
                requires.append(item)
            elif current == "notes":
                notes.append(item)

    # 「- なし」みたいなのは notes からは消してもよい
    notes = [n for n in notes if n not in ("なし", "特になし", "特になし", "特記事項なし")]

    return teaches, requires, notes


def normalize_token(s: str) -> str:
    """比較用のゆるい正規化（空白と一部記号を削るだけ）"""
    t = s.strip()
    t = re.sub(r"\s+", "", t)
    return t


GENERIC_TAILS = ["すること", "できるようになる", "できる", "身につける", "理解する"]
GENERIC_SINGLE = ["理解", "知識", "能力", "スキル", "態度"]


def clean_teaches(raw_teaches, max_n=TEACH_MAX):
    cleaned = []
    seen = set()
    for t in raw_teaches or []:
        if not t:
            continue
        text = str(t).strip()
        if len(text) < 3:
            continue
        if len(text) > 40:
            # 文っぽすぎるのはスキップ
            continue
        if any(kw in text for kw in GENERIC_TAILS):
            continue
        if text in GENERIC_SINGLE:
            continue
        key = normalize_token(text)
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
        if len(cleaned) >= max_n:
            break
    return cleaned


def clean_requires(raw_teaches, raw_requires, max_n=REQ_MAX):
    teaches_norm = [normalize_token(t) for t in (raw_teaches or [])]
    cleaned = []
    seen = set()
    for r in raw_requires or []:
        if not r:
            continue
        text = str(r).strip()
        if len(text) < 3:
            continue
        if len(text) > 40:
            continue
        if any(kw in text for kw in GENERIC_TAILS):
            continue
        if text in GENERIC_SINGLE:
            continue
        rn = normalize_token(text)
        if not rn or rn in seen:
            continue
        # teaches とほぼ同じなら削る（前提ではなく授業内容とみなす）
        if any(rn == tn or rn in tn or tn in rn for tn in teaches_norm):
            continue
        seen.add(rn)
        cleaned.append(text)
        if len(cleaned) >= max_n:
            break
    return cleaned


def main():
    print("=== raw T(c) / R(c) 抽出開始 ===")
    try:
        fin = open(INPUT_JSONL, encoding="utf-8")
    except FileNotFoundError:
        print(f"[FATAL] 入力ファイルが見つかりません: {INPUT_JSONL}")
        return

    with fin, open(OUTPUT_JSONL, "w", encoding="utf-8") as fout:
        for idx, line in enumerate(fin, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[WARN] JSONL {idx} 行目が壊れています: {e}")
                continue

            course_code = rec.get("course_code") or ""
            title = rec.get("title") or ""
            text = rec.get("text") or ""

            print(f"▶ ({idx}) {course_code} {title} ...")

            llm_text = call_ollama_plain(text)
            raw_teaches, raw_requires, llm_notes = parse_sections(llm_text)

            teaches_clean = clean_teaches(raw_teaches, max_n=TEACH_MAX)
            requires_clean = clean_requires(raw_teaches, raw_requires, max_n=REQ_MAX)

            out = {
                "course_code": course_code,
                "title": title,
                "raw_teaches": raw_teaches,
                "raw_requires": raw_requires,
                "teaches_clean": teaches_clean,
                "requires_clean": requires_clean,
            }

            fout.write(json.dumps(out, ensure_ascii=False) + "\n")
            fout.flush()
            time.sleep(SLEEP_SEC)

    print(f"=== 完了: 出力 → {OUTPUT_JSONL} ===")


if __name__ == "__main__":
    main()
