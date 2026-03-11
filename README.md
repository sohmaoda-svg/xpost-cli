<div align="center">

# ⚡ XPost CLI

**AI-powered X (Twitter) post generator for Japanese creators**

[![PyPI version](https://img.shields.io/pypi/v/xpost-cli.svg)](https://pypi.org/project/xpost-cli/)
[![Python](https://img.shields.io/pypi/pyversions/xpost-cli.svg)](https://pypi.org/project/xpost-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](#english) | [日本語](#日本語)

</div>

---

## English

XPost CLI is a command-line tool that uses the OpenAI API to generate compelling X (Twitter) posts in Japanese — with proper tone, hashtags, emojis, and character count validation.

### Features
- 🤖 **AI-generated posts** — GPT-4o-mini with a persona-driven system prompt
- 🎨 **Multiple tones** — professional, casual, humorous, inspirational, educational
- 📋 **History management** — save, list, delete, and export your generated posts
- 📦 **CSV / TXT / JSON export** — take your posts anywhere
- 🔁 **Interactive mode** — REPL-style editing loop

### Quick Start

```bash
pip install xpost-cli
export OPENAI_API_KEY="sk-..."

xpost "The future of AI agents in software development"
```

### Commands

| Command | Description |
|---------|-------------|
| `xpost generate "<topic>"` | Generate post variants |
| `xpost list` | Show saved post history |
| `xpost delete <id>` | Delete a post by ID |
| `xpost clear` | Delete all post history |
| `xpost export --format csv` | Export history to CSV |

---

## 日本語

XPost CLI は、OpenAI API を活用して X（旧Twitter）用の投稿文を自動生成するコマンドラインツールです。

### 特徴
- 🤖 **AIによる投稿文生成** — 日本語特化のシステムプロンプト（敬語禁止・フック重視）
- 🎨 **トーン選択** — professional / casual / humorous / inspirational / educational
- 📋 **履歴管理** — 生成した投稿の保存・一覧・削除・エクスポート
- 📦 **CSV / TXT / JSON エクスポート**
- 🔁 **インタラクティブモード** — 対話形式で条件を変えながら試せる
- ✅ **文字数チェック** — 280文字制限をリアルタイムで可視化

---

## インストール

### PyPI からインストール（推奨）

```bash
pip install xpost-cli
```

### ソースからインストール

```powershell
git clone https://github.com/sohma/xpost-cli
cd xpost-cli
pip install -e .
```

---

## APIキーの設定

```powershell
# PowerShell（セッション内）
$env:OPENAI_API_KEY = "sk-..."

# または .env ファイルに記載
echo "OPENAI_API_KEY=sk-..." > .env
```

---

## 使い方

### 投稿を生成する

```powershell
# 基本
xpost "新しいSaaSプロダクトをローンチした"

# オプション指定
xpost "Pythonの便利Tips" --tone casual --variants 5 --no-hashtags

# インタラクティブモード
xpost --interactive
```

#### オプション一覧（generate）

| オプション | デフォルト | 説明 |
|-----------|---------|------|
| `--tone` | professional | トーン（casual / humorous / inspirational / educational） |
| `--variants, -n` | 3 | 生成するバリエーション数（1〜10） |
| `--no-hashtags` | — | ハッシュタグを無効化 |
| `--no-emojis` | — | 絵文字を無効化 |
| `--context` | — | 追加コンテキスト（任意） |
| `--model` | gpt-4o-mini | 使用する OpenAI モデル |
| `--temperature` | 0.8 | サンプリング温度（0.0〜2.0） |

---

### 履歴を見る（list）

```powershell
xpost list
xpost list --topic "AI" --limit 5
```

---

### 投稿を削除する（delete / clear）

```powershell
# 特定の投稿を削除（IDは list で確認）
xpost delete post_20240101120000_1

# 全て削除（確認プロンプトあり）
xpost clear

# 確認をスキップして全削除
xpost clear --force
```

---

### エクスポート（export）

```powershell
xpost export --format csv --output my_posts.csv
xpost export --format txt
xpost export --format json
```

---

## ライセンス

[MIT License](LICENSE)
