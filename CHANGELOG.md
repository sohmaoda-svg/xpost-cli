# Changelog

All notable changes to xpost-cli will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-03-11

### Added
- **`generate` コマンド**: OpenAI API（gpt-4o-mini）を使って X (Twitter) 投稿文を複数バリエーション生成。
- **`list` コマンド**: `posts.json` に保存された投稿履歴を Rich テーブルで一覧表示。`--topic` でキーワード絞り込み、`--limit` で件数制限に対応。
- **`delete` コマンド**: ID を指定して投稿を削除。削除前に確認プロンプトを表示（`--force` でスキップ可）。
- **`clear` コマンド**: 全投稿履歴を削除（`--force` でスキップ可）。
- **`export` コマンド**: 投稿履歴を `txt` / `json` / `csv` 形式でエクスポート。
- **後方互換**: サブコマンドなしで `xpost "トピック"` のまま使用可能（内部で `generate` に変換）。
- **PyPI パッケージング**: `pyproject.toml` を追加。`pip install xpost-cli` でインストール可能に。
- **`xpost` グローバルコマンド**: インストール後は `xpost` コマンドが PATH で使用可能。

### Fixed
- `parse_posts()` の改行保持バグを修正。投稿内部の改行が失われていた問題を解消。

### Changed
- 日本語 UI 文言（エラーメッセージ・表示ラベル）を整備。

---

*このプロジェクトは [MIT License](LICENSE) の下で公開されています。*
