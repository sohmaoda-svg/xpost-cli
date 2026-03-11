# ChatGPTでX(Twitter)投稿を一発生成するCLIツールを作ってPyPIに公開した

## この記事でわかること

- OpenAI API × CLIツールの実装パターン
- `rich` ライブラリを使ったリッチな CLI UI の作り方
- `pyproject.toml` を使った PyPI パッケージの公開手順
- 日本語に特化したプロンプトエンジニアリング

---

## 作ったもの

**XPost CLI** — X(Twitter)投稿文を AI で一瞬で生成する CLI ツールです。

```bash
pip install xpost-cli
xpost "AIエージェントの将来性について"
```

↑ これだけで、こんな投稿が 3 パターン出てきます。

```
╭─ 案 1  144/280文字 ─────────────────────────────╮
│                                                    │
│  AIエージェントは「道具」じゃなく「同僚」だ。     │
│  もう「AIに仕事を奪われる」じゃない。             │
│  「AIと一緒に成果を出す」時代に入った。           │
│                                                    │
│  この波に乗れるかどうかで、5年後の差は歴然。      │
│                                                    │
│  #AIエージェント #未来の働き方                    │
╰────────────────────────────────────────────────────╯
```

---

## なぜ作ったか

毎日 X に投稿しようとするんですが、文章を考えるのが一番しんどい。

「ネタはある。時間もある。でも**言葉にならない**。」

そんな状態を解決するために作りました。

---

## 技術スタック

| ライブラリ | 用途 |
|-----------|------|
| `openai` | GPT-4o-mini で投稿文を生成 |
| `rich` | ターミナルをリッチに表示 |
| `python-dotenv` | `.env` からAPIキーを読み込む |
| `argparse` | サブコマンド構造 |

---

## プロンプトが肝

普通の AI 生成文章は「〜が期待されます」みたいな**敬語でのっぺりした文章**になりがちです。

これを防ぐために、システムプロンプトに以下のルールを入れました：

```python
SYSTEM_PROMPT = """
あなたはX（Twitter）で数万人のフォロワーを持つカリスマインフルエンサーです。

【絶対ルール】
1. 敬語（です・ます）は一切禁止。「だ・である・しろ」で言い切る。
2. 文字数は280字以内を厳守。
3. 「〜が期待されます」のようなAI特有の曖昧な表現はゴミ箱へ。
4. スマホで読みやすいよう、改行でリズムを作る。
"""
```

この一手間だけで生成される文章のクオリティが段違いになります。

---

## 実装の工夫：後方互換性の維持

途中からサブコマンド構造（`xpost generate / list / delete`）に移行したのですが、
既存ユーザーが `xpost "トピック"` のまま使えるように、
**`sys.argv` を起動時にパッチする**という方法を取りました：

```python
SUBCOMMANDS = {"generate", "list", "delete", "clear", "export"}

def _patch_argv() -> None:
    """サブコマンドなしで直接プロンプトを渡した場合に 'generate' を挿入"""
    if len(sys.argv) <= 1:
        return
    if sys.argv[1] not in SUBCOMMANDS:
        sys.argv.insert(1, "generate")
```

シンプルですが、これで完全な後方互換を維持できます。

---

## PyPI 公開手順

```bash
# パッケージングツールのインストール
pip install build twine

# ビルド
python -m build

# 確認
twine check dist/*

# Test PyPI でテスト（本番前に必ずここで確認）
twine upload --repository testpypi dist/*

# 本番 PyPI に公開
twine upload dist/*
```

`pyproject.toml` のエントリポイント設定で、
インストール後は `xpost` コマンドがグローバルで使えるようになります：

```toml
[project.scripts]
xpost = "xpost_cli:main"
```

---

## 今後の予定

- [ ] Tweepy (X API v2) 連携で実際に自動投稿
- [ ] Webアプリ化（Streamlit or Next.js）
- [ ] スケジュール投稿機能

---

## リポジトリ

👉 https://github.com/sohma/xpost-cli

「使ってみた」「スター付けた」などのフィードバック大歓迎です！
