#!/usr/bin/env python3
"""
ValuSmart AI Daily Poster
毎日定時に SNS 投稿を行うための自動化スクリプト。
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from openai import OpenAI

# xpost_cli から必要な関数をインポート
# パスを通す
sys.path.append(str(Path(__file__).parent))
try:
    from xpost_cli import generate_posts, post_to_x
    # 注意: save_posts, load_posts は JSON 用なので DB 版では使用しない可能性がある
except ImportError as e:
    print(f"Error: xpost_cli.py の読込に失敗しました: {e}")
    sys.exit(1)

# modules/db.py から DB 接続をインポート
# パスを調整 (projects/xpost_cli -> projects/ma-agent)
sys.path.append(str(Path(__file__).parent.parent / "ma-agent"))
try:
    from modules.db import get_connection
except ImportError as e:
    print(f"Warning: modules.db の読込に失敗しました。DB 連携をスキップします: {e}")
    get_connection = None

TOPICS_FILE = Path(__file__).parent / "daily_topics.json"

def run_daily_post():
    # 1. トピックの読み込み
    if not TOPICS_FILE.exists():
        print(f"Error: {TOPICS_FILE} が見つかりません。")
        return

    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    topics = data.get("topics", [])
    last_index = data.get("last_index", -1)
    
    if not topics:
        print("Error: 投稿トピックが空です。")
        return

    # 2. 次のトピックを選択 (ローテーション)
    # GitHub Actions 等の書き込みが保存されない環境に対応するため、DB のレコード数を元にインデックスを決定する
    if get_connection:
        try:
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT count(*) FROM sns_posts WHERE type = 'auto'")
            auto_post_count = c.fetchone()[0]
            next_index = auto_post_count % len(topics)
            conn.close()
            print(f"Index determined by DB (count={auto_post_count}): {next_index}")
        except Exception as e:
            print(f"Warning: DB からのインデックス取得に失敗しました。JSON を使用します: {e}")
            next_index = (last_index + 1) % len(topics)
    else:
        next_index = (last_index + 1) % len(topics)

    topic_data = topics[next_index]
    
    print(f"--- Daily Post Execution: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    print(f"Topic: {topic_data['prompt']}")
    print(f"Tone: {topic_data['tone']}")

    # 3. OpenAI Client の初期化
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY が設定されていません。")
        return
    
    client = OpenAI(api_key=api_key)

    # 4. 投稿文の生成
    try:
        posts = generate_posts(
            client=client,
            prompt=topic_data["prompt"],
            tone=topic_data["tone"],
            num_variants=1,
            include_hashtags=False,
            include_emojis=False,
            additional_context="【重要】Xのスパムフィルター回避のため、「投資」「革命」「絶対」「稼ぐ」などの過激な金融系煽り文句は一切使用しないでください。日常の気づきのような、人間らしく落ち着いたトーンで自然に語ってください。",
            model="gpt-4o-mini"
        )
        if not posts:
            print("Error: 投稿文の生成に失敗しました。")
            return
        
        content = posts[0]
        print(f"Generated Content:\n{content}")
    except Exception as e:
        print(f"Error (Generation): {e}")
        return

    # 5. X への投稿
    try:
        tweet_id, tweet_url = post_to_x(content)
        print(f"Successfully posted to X! URL: {tweet_url}")
    except Exception as e:
        print(f"Error (X Posting): {e}")
        # 投稿失敗時はインデックスを更新せずに終了するか検討が必要だが、
        # ここではログを出力して終了する
        return

    # 6. ステータスの更新と保存
    data["last_index"] = next_index
    with open(TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    # 7. DB に履歴を保存
    if get_connection:
        try:
            conn = get_connection()
            c = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            post_id = f"auto_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            sql = """INSERT INTO sns_posts 
                     (post_id, topic, tone, content, character_count, created_at, posted, tweet_id, tweet_url, posted_at, type)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
            
            c.execute(sql, (
                post_id,
                topic_data["prompt"],
                topic_data["tone"],
                content,
                len(content),
                now,
                True,
                tweet_id,
                tweet_url,
                now,
                "auto"
            ))
            conn.commit()
            conn.close()
            print("Successfully saved to DB!")
        except Exception as e:
            print(f"Warning: DB への保存に失敗しました: {e}")
    else:
        print("Warning: get_connection が利用できないため DB 保存をスキップしました。")

if __name__ == "__main__":
    run_daily_post()
