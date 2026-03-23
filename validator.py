import json
from pathlib import Path
from typing import List, Tuple

def validate_post(content: str, ng_words_path: str = None) -> Tuple[bool, List[str]]:
    """
    X (Twitter) の投稿内容を検証する。
    
    Args:
        content: 検証対象のテキスト
        ng_words_path: NG ワードが記載された JSON ファイルのパス
        
    Returns:
        (passed, errors): 検証結果 (True/False) とエラーメッセージのリスト
    """
    errors = []
    
    # 1. 基本的な長さチェック
    if not content or not content.strip():
        errors.append("投稿内容が空です。")
        return False, errors
    
    char_count = len(content)
    if char_count > 280:
        errors.append(f"文字数オーバーです ({char_count}/280文字)。")

    # 2. NG ワードチェック
    if ng_words_path:
        try:
            p = Path(ng_words_path)
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    ng_words = json.load(f)
                
                for word in ng_words:
                    # 部分一致でチェック (例: 「絶対儲かる」が「絶対に儲かる」に含まれるか)
                    # より厳密には分かち書きや正規表現が必要だが、まずは単純な包含チェック
                    if word in content or any(char in content for char in word if len(word) > 4):
                        # 4文字以上の単語なら、その一部が含まれている場合も警戒（要調整）
                        if word in content:
                            errors.append(f"禁止語句が含まれています: 「{word}」")
        except Exception as e:
            errors.append(f"NG ワードの読み込みに失敗しました: {e}")

    # 3. 形式的なチェック (スパム判定回避)
    # ハッシュタグの数が多すぎないか (5個以上は警告)
    hashtag_count = content.count("#")
    if hashtag_count > 5:
        errors.append(f"ハッシュタグが多すぎます ({hashtag_count}個)。スパム判定のリスクがあります。")
        
    # 感嘆符 (!) の連続使用チェック
    if "!!!" in content:
        errors.append("感嘆符 (!!!) の連続使用はスパム判定のリスクがあります。")

    return len(errors) == 0, errors

if __name__ == "__main__":
    # 簡単なテスト
    test_content = "これは絶対儲かる方法を教えます。誰でも稼げるチャンス！"
    # NGワードパスを仮定 (カレントディレクトリにあると想定してテスト)
    ng_path = "threads-ops/data/knowledge/ng_words.json"
    res, errs = validate_post(test_content, ng_words_path=ng_path)
    print(f"Content: {test_content}")
    print(f"Result: {res}, Errors: {errs}")
