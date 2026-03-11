# XPost CLI 手動テストスクリプト
# 実行前に OPENAI_API_KEY が設定されていることを確認してください

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$scriptDir\.."

Write-Host "=== XPost CLI 手動テストスイート ===" -ForegroundColor Cyan

# ---- テスト 1: 基本的な生成（後方互換） ----
Write-Host "`n[TEST 1] 後方互換: サブコマンドなしで直接プロンプト" -ForegroundColor Yellow
python xpost_cli.py "AIエージェントの可能性" --variants 2 --no-emojis
if ($LASTEXITCODE -ne 0) { Write-Host "FAILED" -ForegroundColor Red; exit 1 }
Write-Host "PASSED" -ForegroundColor Green

# ---- テスト 2: generate サブコマンド ----
Write-Host "`n[TEST 2] generate サブコマンド（casual トーン, ハッシュタグなし）" -ForegroundColor Yellow
python xpost_cli.py generate "Pythonの便利Tips" --tone casual --variants 1 --no-hashtags
if ($LASTEXITCODE -ne 0) { Write-Host "FAILED" -ForegroundColor Red; exit 1 }
Write-Host "PASSED" -ForegroundColor Green

# ---- テスト 3: list コマンド ----
Write-Host "`n[TEST 3] list（全履歴）" -ForegroundColor Yellow
python xpost_cli.py list
if ($LASTEXITCODE -ne 0) { Write-Host "FAILED" -ForegroundColor Red; exit 1 }
Write-Host "PASSED" -ForegroundColor Green

# ---- テスト 4: list --topic 絞り込み ----
Write-Host "`n[TEST 4] list --topic 絞り込み" -ForegroundColor Yellow
python xpost_cli.py list --topic "AI" --limit 3
if ($LASTEXITCODE -ne 0) { Write-Host "FAILED" -ForegroundColor Red; exit 1 }
Write-Host "PASSED" -ForegroundColor Green

# ---- テスト 5: export csv ----
Write-Host "`n[TEST 5] export CSV" -ForegroundColor Yellow
python xpost_cli.py export --format csv --output "$env:TEMP\xpost_test.csv"
if ($LASTEXITCODE -ne 0) { Write-Host "FAILED" -ForegroundColor Red; exit 1 }
Write-Host "PASSED" -ForegroundColor Green

# ---- テスト 6: export txt ----
Write-Host "`n[TEST 6] export TXT" -ForegroundColor Yellow
python xpost_cli.py export --format txt --output "$env:TEMP\xpost_test.txt"
if ($LASTEXITCODE -ne 0) { Write-Host "FAILED" -ForegroundColor Red; exit 1 }
Write-Host "PASSED" -ForegroundColor Green

# ---- テスト 7: export json ----
Write-Host "`n[TEST 7] export JSON" -ForegroundColor Yellow
python xpost_cli.py export --format json --output "$env:TEMP\xpost_test.json"
if ($LASTEXITCODE -ne 0) { Write-Host "FAILED" -ForegroundColor Red; exit 1 }
Write-Host "PASSED" -ForegroundColor Green

# ---- テスト 8: delete（--force で確認スキップ） ----
# ※ 実行前に list でIDを確認して書き換えてください
# Write-Host "`n[TEST 8] delete" -ForegroundColor Yellow
# python xpost_cli.py delete post_XXXX --force

# ---- テスト 9: clear --force ----
Write-Host "`n[TEST 9] clear --force（全削除）" -ForegroundColor Yellow
python xpost_cli.py clear --force
if ($LASTEXITCODE -ne 0) { Write-Host "FAILED" -ForegroundColor Red; exit 1 }
Write-Host "PASSED" -ForegroundColor Green

# ---- テスト 10: 空の list ----
Write-Host "`n[TEST 10] 空の状態で list（エラーなし）" -ForegroundColor Yellow
python xpost_cli.py list
if ($LASTEXITCODE -ne 0) { Write-Host "FAILED" -ForegroundColor Red; exit 1 }
Write-Host "PASSED" -ForegroundColor Green

Write-Host "`n=== 全テスト完了 ✅ ===" -ForegroundColor Cyan
