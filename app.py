# Wikipwdiaから短歌っぽいフレーズを探すスクリプト。
# URLではなく記事名を入力して、その本文をAPIで取る。
# 57577のリズムに近いフレーズをスコア化して上位20件を表示する。

import re
import requests
import streamlit as st
from bs4 import BeautifulSoup
from janome.tokenizer import Tokenizer

st.set_page_config(
    page_title="Wiki短歌pedia",
    page_icon="📚",
    layout="centered",
)

API_URL = "https://ja.wikipedia.org/w/api.php"
USER_AGENT = "WikiTankapedia/0.1 (personal study app)"
tokenizer = Tokenizer()


def fetch_wikipedia_text(title: str) -> str:
    headers = {"User-Agent": USER_AGENT}
    params = {
        "action": "parse",
        "page": title,
        "prop": "text",
        "format": "json",
    }

    response = requests.get(API_URL, params=params, headers=headers, timeout=20)
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        info = data["error"].get("info", "記事を取得できませんでした。")
        raise ValueError(info)

    html = data["parse"]["text"]["*"]
    soup = BeautifulSoup(html, "html.parser")

    texts = []
    for tag in soup.find_all(["p", "li"]):
        text = tag.get_text(" ", strip=True)
        text = re.sub(r"\[\d+\]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            texts.append(text)

    return "\n".join(texts)


def split_candidates(text: str) -> list[str]:
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    sentences = re.split(r"[。！？]", text)

    candidates = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        parts = re.split(r"[、,・]", sentence)
        parts = [p.strip() for p in parts if p.strip()]

        for n in range(2, 6):
            for i in range(len(parts) - n + 1):
                candidates.append("、".join(parts[i:i+n]))

        candidates.append(sentence)

    return candidates


def katakana_to_hiragana(text: str) -> str:
    result = []
    for ch in text:
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:
            result.append(chr(code - 0x60))
        else:
            result.append(ch)
    return "".join(result)


def to_reading(text: str) -> str:
    readings = []
    for token in tokenizer.tokenize(text):
        reading = token.reading
        if reading == "*":
            reading = token.surface
        readings.append(katakana_to_hiragana(reading))
    return "".join(readings)


def count_mora(reading: str) -> int:
    reading = re.sub(r"[^ぁ-んー]", "", reading)
    small_chars = set("ゃゅょぁぃぅぇぉゎ")
    count = 0
    for ch in reading:
        if ch in small_chars:
            continue
        count += 1
    return count


def contains_alnum(text: str) -> bool:
    """半角・全角の英数字を含むかどうか"""
    return re.search(r"[A-Za-z0-9０-９Ａ-Ｚａ-ｚ]", text) is not None


def score_tanka_pattern(reading: str) -> tuple[int, tuple[int, int, int, int, int]]:
    """読みから 5-7-5-7-7 への近さをスコア化する。
    戻り値: (score, (句1, 句2, 句3, 句4, 句5))
    score が小さいほど短歌っぽい。
    """
    mora_text = re.sub(r"[^ぁ-んー]", "", reading)
    n = count_mora(mora_text)

    if n < 5:
        return 10**9, (0, 0, 0, 0, 0)

    best_score = 10**9
    best_pattern = (0, 0, 0, 0, 0)

    # k1, k2, k3, k4 は各句の終端位置（モーラ単位）
    for k1 in range(1, n - 3):
        for k2 in range(k1 + 1, n - 2):
            for k3 in range(k2 + 1, n - 1):
                for k4 in range(k3 + 1, n):
                    p1 = k1
                    p2 = k2 - k1
                    p3 = k3 - k2
                    p4 = k4 - k3
                    p5 = n - k4

                    score = (
                        abs(p1 - 5)
                        + abs(p2 - 7)
                        + abs(p3 - 5)
                        + abs(p4 - 7)
                        + abs(p5 - 7)
                    )

                    # 極端に短い句・長い句を軽く罰する
                    if min(p1, p2, p3, p4, p5) <= 2:
                        score += 3
                    if max(p1, p2, p3, p4, p5) >= 10:
                        score += 3

                    if score < best_score:
                        best_score = score
                        best_pattern = (p1, p2, p3, p4, p5)

    return best_score, best_pattern


def find_tanka_like_candidates(candidates: list[str]) -> list[tuple[str, str, int, int, tuple[int, int, int, int, int]]]:
    results = []
    seen = set()

    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)

        # 英数字を含む候補は除外
        if contains_alnum(cand):
            continue

        reading = to_reading(cand)
        mora = count_mora(reading)

        # まず総音数で粗く絞る
        if not (26 <= mora <= 36):
            continue

        score, pattern = score_tanka_pattern(reading)

        # 5-7-5-7-7 からのズレが大きすぎる候補は除外
        if score <= 4:
            results.append((cand, reading, mora, score, pattern))

    # 57577 に近い順 → 31 に近い順 → 文字列順
    results.sort(key=lambda x: (x[3], abs(x[2] - 31), x[2], x[0]))
    return results[:20]


def run_search(title: str) -> list[tuple[str, str, int, int, tuple[int, int, int, int, int]]]:
    text = fetch_wikipedia_text(title)
    candidates = split_candidates(text)
    return find_tanka_like_candidates(candidates)


st.markdown(
    """
    <style>
    .main-title {
        text-align: center;
        font-size: 2rem;
        font-weight: 700;
        margin-top: 0.5rem;
        margin-bottom: 1.2rem;
    }
    .hero-box {
        max-width: 700px;
        margin: 0 auto 1rem auto;
        padding: 1.2rem 1rem 0.5rem 1rem;
        border-radius: 18px;
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.1);
    }
    .caption {
        text-align: center;
        opacity: 0.8;
        margin-top: -0.25rem;
        margin-bottom: 0.5rem;
        font-size: 0.95rem;
    }
    .result-card {
        padding: 0.9rem 1rem;
        border-radius: 16px;
        border: 1px solid rgba(128,128,128,0.25);
        margin-bottom: 0.8rem;
        background: rgba(255,255,255,0.03);
    }
    .cand {
        font-size: 1.05rem;
        font-weight: 600;
        margin-bottom: 0.3rem;
    }
    .meta {
        font-size: 0.92rem;
        opacity: 0.82;
        word-break: break-word;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Wiki短歌pedia")
st.markdown('<div class="main-title">Wikipediaで短歌を詠もう！</div>', unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="hero-box">', unsafe_allow_html=True)
    with st.form("search_form"):
        title = st.text_input(
            label="記事名",
            placeholder="例：モロカン派",
            label_visibility="collapsed",
        )
        st.markdown('<div class="caption">Wikipediaの記事名を入力してください</div>', unsafe_allow_html=True)
        submitted = st.form_submit_button("Let's 57577！", width="stretch")
    st.markdown('</div>', unsafe_allow_html=True)

if submitted:
    if not title.strip():
        st.warning("記事名を入力してください。")
    else:
        with st.spinner("短歌っぽい候補を探しています…"):
            try:
                results = run_search(title.strip())
            except requests.HTTPError as e:
                st.error(f"Wikipediaへのアクセスでエラーが発生しました: {e}")
                results = []
            except ValueError as e:
                st.error(str(e))
                results = []
            except Exception as e:
                st.error(f"予期しないエラーが発生しました: {e}")
                results = []

        if results:
            st.subheader("短歌っぽい候補 上位20件")
            for i, (cand, reading, mora, score, pattern) in enumerate(results, start=1):
                st.markdown(
                    f'''
                    <div class="result-card">
                        <div class="cand">[{i}] {cand}</div>
                        <div class="meta">よみ: {reading}</div>
                        <div class="meta">音数: {mora}</div>
                        <div class="meta">57577からのズレ: {score}</div>
                        <div class="meta">句割れ推定: {pattern[0]}-{pattern[1]}-{pattern[2]}-{pattern[3]}-{pattern[4]}</div>
                    </div>
                    ''',
                    unsafe_allow_html=True,
                )
        else:
            st.info("短歌っぽい候補が見つかりませんでした。別の記事名でも試してみてください。")
