#!/usr/bin/env python3
"""
XPost CLI - OpenAI を使って X (Twitter) 投稿文を生成・管理する CLI ツール。
v0.2.0 以降: Tweepy を使った X (Twitter) API v2 連携をサポート。
"""

import argparse
import csv
import json
import os
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Tuple

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai がインストールされていません。pip install openai>=1.0.0 を実行してください。", file=sys.stderr)
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    # python-dotenv は任意依存
    pass

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("Error: rich がインストールされていません。pip install rich>=13.0.0 を実行してください。", file=sys.stderr)
    sys.exit(1)

# Tweepy は任意依存: インポート失敗時も --post 以外の機能は正常動作する
try:
    import tweepy  # type: ignore
    TWEEPY_AVAILABLE: bool = True
except ImportError:
    TWEEPY_AVAILABLE = False

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

TWITTER_CHAR_LIMIT = 280
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_NUM_VARIANTS = 3
POSTS_FILE = Path("posts.json")

# 既知のサブコマンド一覧（後方互換処理に使用）
SUBCOMMANDS = {"generate", "list", "delete", "clear", "export", "post"}

# X API v2 認証情報の環境変数名
X_ENV_API_KEY = "X_API_KEY"
X_ENV_API_SECRET = "X_API_SECRET"
X_ENV_ACCESS_TOKEN = "X_ACCESS_TOKEN"
X_ENV_ACCESS_TOKEN_SECRET = "X_ACCESS_TOKEN_SECRET"
X_ENV_BEARER_TOKEN = "X_BEARER_TOKEN"

SYSTEM_PROMPT = textwrap.dedent("""
    あなたはX（Twitter）で数万人のフォロワーを持つカリスマインフルエンサー、兼プロのSNSマーケターです。
    ユーザーのトピックをもとに、思わず手が止まる「フック」の効いた、人間味溢れる投稿を作成してください。

    【絶対ルール】
    1. 敬語（です・ます）は一切禁止。語尾は「だ・である・だろ？・しろ・した。」など、言い切りや問いかけにする。
    2. 文字数は {char_limit} 字以内を厳守（140〜200文字程度がベスト）。
    3. 具体的で感情を揺さぶる言葉を使う。「〜が期待されます」のようなAI特有の曖昧な表現はゴミ箱へ。
    4. スマホで読みやすいよう、適宜改行を入れてリズムを作る。
    5. 各バリエーションには必ず 1. 2. 3. と番号を振ること。
    """).strip()

# ---------------------------------------------------------------------------
# 後方互換処理
# ---------------------------------------------------------------------------

def _patch_argv() -> None:
    """サブコマンドなしで直接プロンプトやフラグが渡された場合に 'generate' を自動挿入する。

    例:
        python xpost_cli.py "AIについて"  →  python xpost_cli.py generate "AIについて"
        python xpost_cli.py --interactive  →  python xpost_cli.py generate --interactive
    """
    if len(sys.argv) <= 1:
        return
    first = sys.argv[1]
    if first not in SUBCOMMANDS:
        sys.argv.insert(1, "generate")


# ---------------------------------------------------------------------------
# 投稿データ管理ユーティリティ
# ---------------------------------------------------------------------------

def load_posts() -> List[dict]:
    """posts.json から投稿リストを読み込む。ファイルが存在しない場合は空リストを返す。"""
    if not POSTS_FILE.exists():
        return []
    try:
        with open(POSTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "posts" in data:
            return data["posts"]
    except Exception:
        pass
    return []


def save_posts(posts: List[dict]) -> None:
    """投稿リストを posts.json に保存する。"""
    with open(POSTS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"posts": posts, "last_updated": datetime.now(timezone.utc).isoformat()},
            f,
            indent=2,
            ensure_ascii=False,
        )


# ---------------------------------------------------------------------------
# X (Twitter) API v2 連携ユーティリティ
# ---------------------------------------------------------------------------

def create_x_client() -> "tweepy.Client":
    """環境変数から X API v2 認証情報を読み込み、Tweepy Client を生成して返す。

    Raises:
        SystemExit: Tweepy が未インストール、または必須の認証情報が不足している場合。
    """
    if not TWEEPY_AVAILABLE:
        console.print(
            "[red bold]Error:[/red bold] tweepy がインストールされていません。\n"
            "[bold]pip install tweepy>=4.14.0[/bold] を実行してください。",
            highlight=False,
        )
        sys.exit(1)

    # 必須環境変数をまとめて検証
    api_key = os.environ.get(X_ENV_API_KEY)
    api_secret = os.environ.get(X_ENV_API_SECRET)
    access_token = os.environ.get(X_ENV_ACCESS_TOKEN)
    access_token_secret = os.environ.get(X_ENV_ACCESS_TOKEN_SECRET)
    bearer_token = os.environ.get(X_ENV_BEARER_TOKEN)

    missing: List[str] = [
        name
        for name, val in [
            (X_ENV_API_KEY, api_key),
            (X_ENV_API_SECRET, api_secret),
            (X_ENV_ACCESS_TOKEN, access_token),
            (X_ENV_ACCESS_TOKEN_SECRET, access_token_secret),
        ]
        if not val
    ]
    if missing:
        console.print(
            "[red bold]Error:[/red bold] X API 認証情報が不足しています。\n"
            f"以下の環境変数が見つかりません: [bold]{', '.join(missing)}[/bold]\n"
            ".env ファイルに設定してください（.env.example を参照）。",
            highlight=False,
        )
        sys.exit(1)

    return tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )


def post_to_x(text: str, dry_run: bool = False) -> Tuple[str, str]:
    """Tweepy を使って X (Twitter) に投稿し、ツイート ID と URL を返す。

    Args:
        text: 投稿するテキスト（280文字以内）。
        dry_run: True の場合、実際の API 呼び出しを行わずにシミュレーションする。

    Returns:
        (tweet_id, tweet_url) のタプル。

    Raises:
        SystemExit: 投稿に失敗した場合。
    """
    # 文字数チェック（API 呼び出し前にバリデーション）
    if len(text) > TWITTER_CHAR_LIMIT:
        console.print(
            f"[red bold]Error:[/red bold] 投稿文が {TWITTER_CHAR_LIMIT} 文字を超えています"
            f"（{len(text)} 文字）。",
            highlight=False,
        )
        sys.exit(1)

    if dry_run:
        console.print("[yellow][DRY RUN][/yellow] X への投稿をスキップしました（dry-run モード）。")
        return "mock_id_dry_run", "https://x.com/mock_status_dry_run"

    x_client = create_x_client()

    try:
        response = x_client.create_tweet(text=text)
    except Exception as exc:
        msg = str(exc)
        if "403" in msg:
            console.print(f"[red bold]X API エラー (403 Forbidden):[/red bold] {exc}", highlight=False)
            console.print("[yellow]ヒント:[/yellow] 以下の可能性があります：")
            console.print("  1. App の権限が 'Read and write' になっていない")
            console.print("  2. API キーまたはトークンが古い or 無効")
            console.print("  3. 投稿内容がスパムフィルター（NG語等）に抵触した")
            console.print("  4. 24時間の投稿制限（Free Tier: 50件程度）に達した")
        elif "429" in msg or "Rate limit" in msg:
            console.print(f"[red bold]X API エラー (429 Rate Limit):[/red bold] {exc}", highlight=False)
        else:
            console.print(f"[red bold]X API エラー:[/red bold] {exc}", highlight=False)
        sys.exit(1)

    # Tweepy v2 レンスポンスからツイート ID を取得
    tweet_id: str = str(response.data["id"])
    tweet_url: str = f"https://x.com/i/web/status/{tweet_id}"
    return tweet_id, tweet_url


# ---------------------------------------------------------------------------
# 投稿生成ロジック
# ---------------------------------------------------------------------------

def build_user_message(
    prompt: str,
    tone: str,
    num_variants: int,
    include_hashtags: bool,
    include_emojis: bool,
    additional_context: Optional[str] = None,
) -> str:
    """モデルに送るユーザーメッセージ（指示文）を構築する。"""
    parts = [f"以下のトピックについて、{num_variants} 個の投稿案を作成しろ：\n\n{prompt}"]

    tone_map = {
        "professional": "自信に満ちたプロの鋭い視点",
        "casual": "本音で語る親しみやすい口調",
        "humorous": "ウィットに富んだ皮肉めいた口調",
        "inspirational": "熱く魂を揺さぶる口調",
        "educational": "有益な知識をズバッと教える口調",
    }
    parts.append(f"トーン：{tone_map.get(tone, '魅力的で刺さる口調')}")

    if not include_hashtags:
        parts.append("ハッシュタグは入れるな。")
    else:
        parts.append("関連するハッシュタグを2〜3個、文末に添えろ。")

    if not include_emojis:
        parts.append("絵文字は使うな。")
    else:
        parts.append("絵文字を効果的に（うるさくない程度に）使え。")

    if additional_context:
        parts.append(f"追加コンテキスト：{additional_context}")

    parts.append(f"忘れるな。各投稿は必ず {TWITTER_CHAR_LIMIT} 文字以内に収めること。")
    return "\n".join(parts)


def generate_posts(
    client: OpenAI,
    prompt: str,
    tone: str = "professional",
    num_variants: int = DEFAULT_NUM_VARIANTS,
    include_hashtags: bool = True,
    include_emojis: bool = True,
    additional_context: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.8,
) -> List[str]:
    """OpenAI API を呼び出して投稿文のリストを返す。"""
    system_message = SYSTEM_PROMPT.format(char_limit=TWITTER_CHAR_LIMIT)
    user_message = build_user_message(
        prompt=prompt,
        tone=tone,
        num_variants=num_variants,
        include_hashtags=include_hashtags,
        include_emojis=include_emojis,
        additional_context=additional_context,
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
        temperature=temperature,
        max_tokens=1024,
    )

    raw_text = response.choices[0].message.content.strip()
    return parse_posts(raw_text, num_variants)


def parse_posts(raw_text: str, expected: int) -> List[str]:
    """モデルのレスポンスを個別の投稿文リストにパースする。

    番号付きリスト（1. / 2. / 10. など）を区切りとして認識し、
    投稿内部の改行はそのまま保持する（旧実装のバグを修正）。
    """
    lines = raw_text.splitlines()
    posts: List[str] = []
    current: List[str] = []

    def flush() -> None:
        """current バッファを posts に追加してクリアする。"""
        if current:
            posts.append("\n".join(current).strip())
            current.clear()

    for line in lines:
        stripped = line.strip()

        # 番号プレフィックス（"1." / "2)" / "10." など）を検出
        is_new_post = False
        content_start = 0
        if stripped and stripped[0].isdigit():
            for sep_len in (2, 3):
                if (
                    len(stripped) >= sep_len
                    and stripped[sep_len - 1] in ".):,"
                    and (sep_len == 2 or stripped[: sep_len - 1].isdigit())
                ):
                    is_new_post = True
                    content_start = sep_len
                    break

        if is_new_post:
            flush()
            rest = stripped[content_start:].strip()
            if rest:
                current.append(rest)
        elif not stripped:
            # 空行はポスト区切りとして扱う（current が空でない場合のみ flush）
            flush()
        else:
            current.append(stripped)

    flush()

    if not posts:
        posts = [raw_text.strip()]

    return posts[:expected] if len(posts) >= expected else posts


# ---------------------------------------------------------------------------
# 表示ヘルパー
# ---------------------------------------------------------------------------

console = Console()


def display_posts(posts: List[str], show_char_count: bool = True) -> None:
    """Rich Panel を使って生成された投稿を見やすく表示する。"""
    console.print()
    for i, post in enumerate(posts, start=1):
        char_count = len(post)
        over_limit = char_count > TWITTER_CHAR_LIMIT
        count_color = "red bold" if over_limit else "green"
        count_label = (
            f"[{count_color}]{char_count}/{TWITTER_CHAR_LIMIT}文字"
            f"{'  ⚠ 超過' if over_limit else ''}[/{count_color}]"
        )
        title = f"[bold cyan]案 {i}[/bold cyan]  {count_label if show_char_count else ''}"
        console.print(Panel(Text(post), title=title, border_style="cyan", padding=(1, 2)))
    console.print()


def display_summary(posts: List[str]) -> None:
    """全バリアントの要約（文字数・ステータス・プレビュー）を表示する。"""
    console.print("[bold]サマリー:[/bold]")
    for i, post in enumerate(posts, start=1):
        status = "✅" if len(post) <= TWITTER_CHAR_LIMIT else "❌ 超過"
        preview = post.replace("\n", " ")
        console.print(
            f"  {i}. {len(post):>3}文字  {status}  {preview[:60]}{'…' if len(preview) > 60 else ''}"
        )
    console.print()


# ---------------------------------------------------------------------------
# サブコマンド: generate（投稿生成）
# ---------------------------------------------------------------------------

def cmd_generate(args) -> None:
    """投稿文を生成して表示・posts.json に保存する。"""
    # APIキー解決
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        console.print(
            "[red bold]Error:[/red bold] OpenAI API キーが見つかりません。\n"
            "[bold]OPENAI_API_KEY[/bold] 環境変数を設定するか、[bold]--api-key[/bold] で渡してください。",
            highlight=False,
        )
        sys.exit(1)

    if not 0.0 <= args.temperature <= 2.0:
        console.print("[red]Error: --temperature は 0.0〜2.0 の範囲で指定してください。[/red]")
        sys.exit(1)

    if args.variants < 1 or args.variants > 10:
        console.print("[red]Error: --variants は 1〜10 の範囲で指定してください。[/red]")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    # インタラクティブモード
    if args.interactive:
        interactive_mode(client, model=args.model)
        return

    if not args.prompt:
        console.print("[red]Error: トピックを入力するか、--interactive モードを使ってください。[/red]")
        sys.exit(1)

    console.print(f"\n[bold green]{args.variants} パターンを生成中…[/bold green]\n")

    try:
        posts = generate_posts(
            client=client,
            prompt=args.prompt,
            tone=args.tone,
            num_variants=args.variants,
            include_hashtags=args.hashtags,
            include_emojis=args.emojis,
            additional_context=args.context,
            model=args.model,
            temperature=args.temperature,
        )
    except Exception as exc:
        console.print(f"[red]OpenAI API 呼び出しエラー: {exc}[/red]")
        sys.exit(1)

    display_posts(posts, show_char_count=args.show_char_count)
    display_summary(posts)

    # posts.json に保存
    existing = load_posts()
    now = datetime.now(timezone.utc)
    new_records: List[dict] = []
    for i, content in enumerate(posts):
        post_id = f"post_{now.strftime('%Y%m%d%H%M%S')}_{i + 1}"
        record: dict = {
            "id": post_id,
            "topic": args.prompt,
            "tone": args.tone,
            "model": args.model,
            "content": content,
            "character_count": len(content),
            "created_at": now.isoformat(),
            "posted": False,
            "tweet_id": None,
            "tweet_url": None,
            "posted_at": None,
        }
        existing.append(record)
        new_records.append(record)

    try:
        save_posts(existing)
        console.print(f"[green]✅ {len(new_records)} 件を posts.json に保存しました[/green]")
    except Exception as e:
        console.print(f"[red]保存に失敗しました: {e}[/red]")

    # --post フラグが指定された場合、選択した投稿を X に直接投稿する
    if getattr(args, "post", False):
        _post_selected_variant(new_records, existing, dry_run=getattr(args, "dry_run", False))


# ---------------------------------------------------------------------------
# 投稿選択 & X 送信ヘルパー
# ---------------------------------------------------------------------------

def _post_selected_variant(new_records: List[dict], all_posts: List[dict], dry_run: bool = False) -> None:
    """生成した投稿バリアントからユーザーに選ばせ、X に投稿してレコードを更新する。

    Args:
        new_records: 今回生成したレコードのリスト（posts.json 未更新 ID を含む）。
        all_posts: 既存のすべての投稿レコード（更新後に保存する対象）。
        dry_run: API 呼び出しをスキップするかどうか。
    """
    if len(new_records) == 1:
        # バリアントが 1 件の場合は選択をスキップして自動投稿
        selected = new_records[0]
    else:
        # 複数バリアントの場合は番号入力で選択
        console.print(
            "\n[bold yellow]どの案を X に投稿しますか？[/bold yellow] "
            f"番号を入力してください（1〜{len(new_records)}）："
        )
        for i, rec in enumerate(new_records, start=1):
            preview = rec["content"].replace("\n", " ")[:60]
            console.print(f"  [cyan]{i}.[/cyan] {preview}…")

        while True:
            choice_str = Prompt.ask("[bold]投稿する案の番号[/bold]")
            try:
                choice = int(choice_str)
                if 1 <= choice <= len(new_records):
                    break
            except ValueError:
                pass
            console.print(f"[red]1〜{len(new_records)} の数字を入力してください。[/red]")

        selected = new_records[choice - 1]

    # 確認プロンプト
    console.print(
        Panel(
            selected["content"],
            title="[bold cyan]X に投稿する内容[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    if not Confirm.ask("[bold green]この内容で X に投稿しますか？[/bold green]", default=True):
        console.print("[dim]投稿をキャンセルしました。[/dim]")
        return

    # X API 経由で投稿
    console.print("[bold green]X に投稿中…[/bold green]")
    tweet_id, tweet_url = post_to_x(selected["content"], dry_run=dry_run)

    # レコードを更新して保存（dry_run の場合はスキップ）
    if not dry_run:
        posted_at = datetime.now(timezone.utc).isoformat()
        for rec in all_posts:
            if rec.get("id") == selected["id"]:
                rec["posted"] = True
                rec["tweet_id"] = tweet_id
                rec["tweet_url"] = tweet_url
                rec["posted_at"] = posted_at
                break

        try:
            save_posts(all_posts)
        except Exception as e:
            console.print(f"[red]保存に失敗しました: {e}[/red]")
    else:
        console.print("[yellow][DRY RUN][/yellow] 投稿ステータスの更新をスキップしました。")

    console.print(
        f"[bold green]✅ X に投稿しました！[/bold green]\n"
        f"[dim]ツイート ID: {tweet_id}[/dim]\n"
        f"[bold]URL:[/bold] {tweet_url}"
    )


# ---------------------------------------------------------------------------
# サブコマンド: post（保存済み投稿を X に送信）
# ---------------------------------------------------------------------------

def cmd_post(args) -> None:
    """posts.json に保存済みの投稿を ID 指定で X (Twitter) に投稿する。"""
    posts = load_posts()
    target_id: str = args.post_id
    target = next((p for p in posts if p.get("id") == target_id), None)

    if target is None:
        console.print(f"[red]ID「{target_id}」の投稿が見つかりませんでした。[/red]")
        console.print("[dim]ヒント: `xpost list` で ID を確認できます。[/dim]")
        sys.exit(1)

    # 既投稿チェック
    if target.get("posted") and not getattr(args, "force", False):
        console.print(
            f"[yellow]⚠️  この投稿はすでに X に投稿済みです。[/yellow]\n"
            f"  ツイート URL: {target.get('tweet_url', '不明')}\n"
            "再投稿するには [bold]--force[/bold] フラグを付けてください。"
        )
        sys.exit(1)

    # 投稿内容を表示して確認
    console.print(
        Panel(
            target["content"],
            title="[bold cyan]X に投稿する内容[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    if not getattr(args, "force", False):
        if not Confirm.ask("[bold green]この内容で X に投稿しますか？[/bold green]", default=True):
            console.print("[dim]投稿をキャンセルしました。[/dim]")
            return

    # X API 経由で投稿
    console.print("[bold green]X に投稿中…[/bold green]")
    tweet_id, tweet_url = post_to_x(target["content"], dry_run=getattr(args, "dry_run", False))

    # レコードを更新して保存（dry_run の場合はスキップ）
    if not getattr(args, "dry_run", False):
        posted_at = datetime.now(timezone.utc).isoformat()
        for rec in posts:
            if rec.get("id") == target_id:
                rec["posted"] = True
                rec["tweet_id"] = tweet_id
                rec["tweet_url"] = tweet_url
                rec["posted_at"] = posted_at
                break

        try:
            save_posts(posts)
        except Exception as e:
            console.print(f"[red]保存に失敗しました: {e}[/red]")
    else:
        console.print("[yellow][DRY RUN][/yellow] 投稿ステータスの更新をスキップしました。")

    console.print(
        f"[bold green]✅ X に投稿しました！[/bold green]\n"
        f"[dim]ツイート ID: {tweet_id}[/dim]\n"
        f"[bold]URL:[/bold] {tweet_url}"
    )


# ---------------------------------------------------------------------------
# サブコマンド: list（履歴一覧）
# ---------------------------------------------------------------------------

def cmd_list(args) -> None:
    """保存済みの投稿を Rich テーブルで一覧表示する。"""
    all_posts = load_posts()
    if not all_posts:
        console.print(
            "[yellow]保存された投稿がありません。"
            "まず `xpost generate <トピック>` で投稿を生成してください。[/yellow]"
        )
        return

    # キーワード絞り込み
    filtered = all_posts
    if args.topic:
        keyword = args.topic.lower()
        filtered = [
            p for p in all_posts
            if keyword in p.get("topic", "").lower()
            or keyword in p.get("content", "").lower()
        ]
        if not filtered:
            console.print(f"[yellow]「{args.topic}」に一致する投稿が見つかりませんでした。[/yellow]")
            return

    # 最新順にソートして件数制限
    posts_to_show = list(reversed(filtered))[: args.limit]
    total = len(filtered)

    table = Table(
        title=f"📋 投稿履歴（{len(posts_to_show)}/{total} 件表示）",
        border_style="cyan",
        show_lines=True,
    )
    table.add_column("ID", style="dim", no_wrap=True, min_width=28)
    table.add_column("トピック", min_width=16)
    table.add_column("トーン", min_width=12)
    table.add_column("文字数", justify="right", min_width=6)
    table.add_column("X投稿", justify="center", min_width=5)
    table.add_column("内容（抜粋）", min_width=36)
    table.add_column("生成日時", min_width=19)

    for post in posts_to_show:
        char_count = post.get("character_count", len(post.get("content", "")))
        count_style = "red" if char_count > TWITTER_CHAR_LIMIT else "green"
        # X 投稿済みフラグを表示
        posted_mark = "[green]✓[/green]" if post.get("posted") else "[dim]–[/dim]"
        preview = post.get("content", "").replace("\n", " ")
        created = post.get("created_at", "")[:19].replace("T", " ")
        topic_text = post.get("topic", "")
        table.add_row(
            post.get("id", ""),
            topic_text[:16] + ("…" if len(topic_text) > 16 else ""),
            post.get("tone", ""),
            f"[{count_style}]{char_count}[/{count_style}]",
            posted_mark,
            preview[:36] + ("…" if len(preview) > 36 else ""),
            created,
        )

    console.print()
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# サブコマンド: delete（投稿削除）
# ---------------------------------------------------------------------------

def cmd_delete(args) -> None:
    """ID を指定して投稿を削除する。"""
    posts = load_posts()
    target_id = args.post_id
    target = next((p for p in posts if p.get("id") == target_id), None)

    if target is None:
        console.print(f"[red]ID「{target_id}」の投稿が見つかりませんでした。[/red]")
        console.print("[dim]ヒント: `xpost list` で ID を確認できます。[/dim]")
        sys.exit(1)

    preview = target.get("content", "").replace("\n", " ")
    console.print(
        Panel(
            f"[bold]ID:[/bold] {target_id}\n"
            f"[bold]トピック:[/bold] {target.get('topic', '')}\n"
            f"[bold]内容（抜粋）:[/bold] {preview[:80]}{'…' if len(preview) > 80 else ''}",
            title="[yellow bold]⚠️  削除対象の投稿[/yellow bold]",
            border_style="yellow",
        )
    )

    if not args.force:
        confirmed = Confirm.ask("[bold red]本当に削除しますか？[/bold red]", default=False)
        if not confirmed:
            console.print("[dim]削除をキャンセルしました。[/dim]")
            return

    updated = [p for p in posts if p.get("id") != target_id]
    save_posts(updated)
    console.print(f"[green]✅ 投稿「{target_id}」を削除しました。[/green]")


# ---------------------------------------------------------------------------
# サブコマンド: clear（全削除）
# ---------------------------------------------------------------------------

def cmd_clear(args) -> None:
    """全投稿履歴を削除する。"""
    posts = load_posts()
    count = len(posts)
    if count == 0:
        console.print("[yellow]削除する投稿がありません。[/yellow]")
        return

    if not args.force:
        console.print(f"[yellow bold]⚠️  {count} 件の投稿を全て削除しようとしています。[/yellow bold]")
        confirmed = Confirm.ask(
            "[bold red]本当に全て削除しますか？この操作は取り消せません。[/bold red]",
            default=False,
        )
        if not confirmed:
            console.print("[dim]削除をキャンセルしました。[/dim]")
            return

    save_posts([])
    console.print(f"[green]✅ {count} 件の投稿を全て削除しました。[/green]")


# ---------------------------------------------------------------------------
# サブコマンド: export（エクスポート）
# ---------------------------------------------------------------------------

def cmd_export(args) -> None:
    """投稿履歴を txt / json / csv 形式でファイルに書き出す。"""
    posts = load_posts()
    if not posts:
        console.print("[yellow]エクスポートする投稿がありません。[/yellow]")
        return

    fmt = args.format.lower()

    # 出力ファイルパスの決定
    if args.output:
        out_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d")
        out_path = Path(f"xpost_export_{timestamp}.{fmt}")

    try:
        if fmt == "json":
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"posts": posts}, f, indent=2, ensure_ascii=False)

        elif fmt == "txt":
            with open(out_path, "w", encoding="utf-8") as f:
                for i, post in enumerate(posts, start=1):
                    f.write(f"{'=' * 60}\n")
                    f.write(f"投稿 {i}  |  ID: {post.get('id', '')}\n")
                    f.write(f"トピック: {post.get('topic', '')}\n")
                    f.write(f"生成日時: {post.get('created_at', '')}\n")
                    f.write(f"{'=' * 60}\n\n")
                    f.write(post.get("content", ""))
                    f.write("\n\n")

        elif fmt == "csv":
            fieldnames = [
                "id", "topic", "tone", "model",
                "content", "character_count", "created_at",
            ]
            with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(posts)

        console.print(
            f"[green]✅ {len(posts)} 件を [bold]{out_path}[/bold] に出力しました"
            f"（{fmt.upper()} 形式）[/green]"
        )

    except Exception as e:
        console.print(f"[red]エクスポートに失敗しました: {e}[/red]")
        sys.exit(1)


# ---------------------------------------------------------------------------
# インタラクティブモード
# ---------------------------------------------------------------------------

def interactive_mode(client: OpenAI, model: str) -> None:
    """対話型 REPL モードで投稿を生成する。"""
    console.print(
        Panel(
            "[bold magenta]XPost CLI – インタラクティブモード[/bold magenta]\n"
            "AIを使ってX(Twitter)投稿文を生成します。\n"
            "[bold]exit[/bold] または [bold]quit[/bold] で終了。",
            border_style="magenta",
        )
    )

    while True:
        console.rule()
        prompt_text = Prompt.ask("\n[bold yellow]トピック・アイデアを入力[/bold yellow]")

        if prompt_text.lower() in {"exit", "quit", "q"}:
            console.print("[bold magenta]お疲れ様でした！👋[/bold magenta]")
            break

        if not prompt_text.strip():
            console.print("[red]トピックは必須です。もう一度入力してください。[/red]")
            continue

        tone = Prompt.ask("[bold]トーン/スタイル[/bold]", default="professional", show_default=True)
        num_variants_str = Prompt.ask(
            "[bold]バリエーション数[/bold]",
            default=str(DEFAULT_NUM_VARIANTS),
            show_default=True,
        )
        try:
            num_variants = int(num_variants_str)
            if num_variants < 1 or num_variants > 10:
                raise ValueError
        except ValueError:
            console.print("[red]無効な数値です。デフォルト (3) を使用します。[/red]")
            num_variants = DEFAULT_NUM_VARIANTS

        include_hashtags = Confirm.ask("[bold]ハッシュタグを含める？[/bold]", default=True)
        include_emojis = Confirm.ask("[bold]絵文字を使う？[/bold]", default=True)
        additional_context = Prompt.ask(
            "[bold]追加コンテキスト[/bold] (なければ Enter)", default=""
        )

        console.print("\n[bold green]生成中…[/bold green]")
        try:
            posts = generate_posts(
                client=client,
                prompt=prompt_text,
                tone=tone,
                num_variants=num_variants,
                include_hashtags=include_hashtags,
                include_emojis=include_emojis,
                additional_context=additional_context or None,
                model=model,
            )
        except Exception as exc:
            console.print(f"[red]OpenAI API エラー: {exc}[/red]")
            continue

        display_posts(posts)
        display_summary(posts)

        if Confirm.ask("[bold]同じトピックでさらに生成する？[/bold]", default=False):
            try:
                more_posts = generate_posts(
                    client=client,
                    prompt=prompt_text,
                    tone=tone,
                    num_variants=num_variants,
                    include_hashtags=include_hashtags,
                    include_emojis=include_emojis,
                    additional_context=additional_context or None,
                    model=model,
                    temperature=0.95,
                )
                console.print("\n[bold cyan]追加バリエーション:[/bold cyan]")
                display_posts(more_posts)
                display_summary(more_posts)
            except Exception as exc:
                console.print(f"[red]エラー: {exc}[/red]")


# ---------------------------------------------------------------------------
# CLI パーサー構築
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """メインの ArgumentParser とすべてのサブコマンドパーサーを構築する。"""
    parser = argparse.ArgumentParser(
        prog="xpost",
        description="AI を活用して X (Twitter) 投稿文を生成・管理する CLI ツール。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            使用例:
              xpost "新製品のSaaSをローンチした"
              xpost generate "Pythonのコツ" --tone casual --variants 5
              xpost generate "AIの未来" --post
              xpost post post_20240101120000_1
              xpost list --topic "AI" --limit 10
              xpost delete post_20240101120000_1
              xpost clear --force
              xpost export --format csv --output posts.csv
              xpost --interactive
        """),
    )

    subparsers = parser.add_subparsers(dest="command")

    # ---- generate サブコマンド ----
    gen = subparsers.add_parser(
        "generate",
        help="投稿文を生成する（デフォルト動作）",
        description="OpenAI API を使って X 投稿文を生成します。",
    )
    gen.add_argument("prompt", nargs="?", help="投稿のトピック・アイデア。--interactive なら省略可。")
    gen.add_argument("-i", "--interactive", action="store_true", help="対話型モードで起動する。")
    gen.add_argument(
        "--tone", default="professional", metavar="TONE",
        help="トーン: professional / casual / humorous / inspirational / educational。デフォルト: professional。",
    )
    gen.add_argument(
        "--variants", "-n", type=int, default=DEFAULT_NUM_VARIANTS, metavar="N",
        help=f"生成するバリエーション数（1〜10）。デフォルト: {DEFAULT_NUM_VARIANTS}。",
    )
    gen.add_argument("--no-hashtags", dest="hashtags", action="store_false", default=True,
                     help="ハッシュタグを無効化する。")
    gen.add_argument("--no-emojis", dest="emojis", action="store_false", default=True,
                     help="絵文字を無効化する。")
    gen.add_argument("--context", default=None, metavar="TEXT", help="追加コンテキスト（任意）。")
    gen.add_argument("--model", default=DEFAULT_MODEL, metavar="MODEL",
                     help=f"使用する OpenAI モデル。デフォルト: {DEFAULT_MODEL}。")
    gen.add_argument(
        "--temperature", type=float, default=0.8, metavar="FLOAT",
        help="サンプリング温度（0.0〜2.0）。高いほど多様な表現。デフォルト: 0.8。",
    )
    gen.add_argument("--api-key", default=None, metavar="KEY",
                     help="OpenAI API キー。省略時は OPENAI_API_KEY 環境変数を使用。")
    gen.add_argument("--no-char-count", dest="show_char_count", action="store_false", default=True,
                     help="文字数カウントを非表示にする。")
    gen.add_argument(
        "--post", dest="post", action="store_true", default=False,
        help="生成後に選択した投稿を X (Twitter) に直接送信する（要: X API 認証情報）。",
    )
    gen.add_argument("--dry-run", action="store_true", help="実際の API 呼び出しを行わずに投稿シミュレーションを行う。")

    # ---- post サブコマンド ----
    pst = subparsers.add_parser(
        "post",
        help="保存済みの投稿を ID 指定で X (Twitter) に送信する。",
        description="posts.json に保存されている投稿を X API v2 経由で投稿します。",
    )
    pst.add_argument("post_id", help="投稿する投稿の ID（`xpost list` で確認可）。")
    pst.add_argument(
        "--force", "-f", action="store_true",
        help="確認プロンプトをスキップ、および既投稿の投稿も再投稿する。",
    )
    pst.add_argument("--dry-run", action="store_true", help="実際の API 呼び出しを行わずに投稿シミュレーションを行う。")

    # ---- list サブコマンド ----
    lst = subparsers.add_parser("list", help="保存済みの投稿を一覧表示する。")
    lst.add_argument("--topic", default=None, metavar="KEYWORD",
                     help="トピックまたは内容でキーワード絞り込み。")
    lst.add_argument("--limit", type=int, default=20, metavar="N",
                     help="表示件数の上限（最新順）。デフォルト: 20。")

    # ---- delete サブコマンド ----
    dlt = subparsers.add_parser("delete", help="ID を指定して投稿を削除する。")
    dlt.add_argument("post_id", help="削除する投稿の ID（`xpost list` で確認可）。")
    dlt.add_argument("--force", "-f", action="store_true", help="確認プロンプトをスキップする。")

    # ---- clear サブコマンド ----
    clr = subparsers.add_parser("clear", help="全ての投稿履歴を削除する。")
    clr.add_argument("--force", "-f", action="store_true", help="確認プロンプトをスキップする。")

    # ---- export サブコマンド ----
    exp = subparsers.add_parser("export", help="投稿履歴をファイルに書き出す。")
    exp.add_argument(
        "--format", default="json", choices=["txt", "json", "csv"],
        help="出力フォーマット: txt / json / csv。デフォルト: json。",
    )
    exp.add_argument("--output", default=None, metavar="FILE",
                     help="出力ファイルパス。省略時は xpost_export_YYYYMMDD.{ext}。")

    return parser


# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI エントリポイント。サブコマンドを解析してハンドラーにディスパッチする。"""
    _patch_argv()
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "generate": cmd_generate,
        "list": cmd_list,
        "delete": cmd_delete,
        "clear": cmd_clear,
        "export": cmd_export,
        "post": cmd_post,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(0)

    handler(args)


if __name__ == "__main__":
    main()
