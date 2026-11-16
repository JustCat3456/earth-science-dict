"""地球科学IME辞書ビルダーの単体テスト。"""

from __future__ import annotations

import plistlib
from pathlib import Path

from src.build_dict import (
  DictEntry,
  build_all,
  deduplicate_entries,
  validate_reading,
)
from src.install_mozc import (
  encode_length_delimited,
  encode_user_dictionary,
  extract_dictionary_name,
  install_to_mozc,
  parse_existing_storage,
)

BASE_DIR = Path(__file__).resolve().parent.parent


def test_validate_reading() -> None:
  """ひらがな・長音のみの読みを正しく判定できること。"""
  assert validate_reading("せいすいあつへいこう")
  assert validate_reading("くりのめーたー")
  assert not validate_reading("カタカナ")
  assert not validate_reading("HR図")
  assert not validate_reading("せいすいあつ へいこう")
  assert not validate_reading("")


def test_deduplicate_entries() -> None:
  """(reading, word) の完全重複が除去されること。"""
  entries = [
    DictEntry("そうこう", "走向", "名詞", "解説1", "solid_earth"),
    DictEntry("そうこう", "走向", "名詞", "解説2", "solid_earth"),
    DictEntry("けいしゃ", "傾斜", "名詞", "解説3", "solid_earth"),
  ]
  unique = deduplicate_entries(entries)
  assert len(unique) == 2
  assert unique[0].word == "走向"
  assert unique[1].word == "傾斜"


def test_build_all_outputs_valid_formats() -> None:
  """実データから全OS向け辞書が正しいフォーマットで生成されること。"""
  counts = build_all(BASE_DIR)
  assert counts["solid_earth"] > 0
  assert counts["atmosphere_ocean"] > 0
  assert counts["space_planetary"] > 0
  assert counts["all"] > 0

  dist_dir = BASE_DIR / "dist"

  # 1. Google日本語入力 / Mozc (UTF-8, LF)
  mozc_file = dist_dir / "google_mozc" / "earth_science_all_mozc.txt"
  assert mozc_file.exists()
  mozc_bytes = mozc_file.read_bytes()
  assert not mozc_bytes.startswith(b"\xef\xbb\xbf")
  assert b"\r\n" not in mozc_bytes
  mozc_text = mozc_bytes.decode("utf-8")
  assert "せいすいあつへいこう\t静水圧平衡\t名詞" in mozc_text
  assert "ちそうのそうこう\t地層の走向\t名詞" in mozc_text

  # 2. Windows Microsoft IME (UTF-16LE BOM, CRLF)
  msime_file = dist_dir / "windows_ms_ime" / "earth_science_all_msime.txt"
  assert msime_file.exists()
  msime_bytes = msime_file.read_bytes()
  assert msime_bytes.startswith(b"\xff\xfe")
  msime_text = msime_bytes[2:].decode("utf-16-le")
  assert "\r\n" in msime_text
  assert "せいすいあつへいこう\t静水圧平衡\t名詞" in msime_text
  assert "ちそうのそうこう\t地層の走向\t名詞" in msime_text

  # 3. macOS ユーザ辞書 (.plist)
  plist_file = dist_dir / "macos_ime" / "earth_science_all_macos.plist"
  assert plist_file.exists()
  plist_data = plistlib.loads(plist_file.read_bytes())
  assert isinstance(plist_data, list)
  pairs = {(item["shortcut"], item["phrase"]) for item in plist_data}
  assert ("せいすいあつへいこう", "静水圧平衡") in pairs
  assert ("ちそうのそうこう", "地層の走向") in pairs

  # 4. 用語集Markdown
  glossary_file = dist_dir / "earth_science_glossary.md"
  assert glossary_file.exists()
  glossary_text = glossary_file.read_text(encoding="utf-8")
  assert "静水圧平衡" in glossary_text
  assert "地層の走向" in glossary_text


def test_install_to_mozc_preserves_existing_and_is_idempotent(tmp_path: Path) -> None:
  """既存のMozcユーザー辞書を保持しつつ、地球科学辞書を冪等に登録できること。"""
  db_path = tmp_path / "user_dictionary.db"
  existing_dict = encode_user_dictionary(
    "ユーザー辞書 1",
    [DictEntry("はるき", "遼樹", "名詞", "", "custom")],
  )
  db_path.write_bytes(encode_length_delimited(2, existing_dict))

  # 1回目と2回目で結果が同じ（重複しない）こと
  counts1 = install_to_mozc(BASE_DIR, db_path)
  counts2 = install_to_mozc(BASE_DIR, db_path)
  assert counts1 == counts2
  assert db_path.with_suffix(".db.bak").exists()

  # 既存の "ユーザー辞書 1" が残っていること
  remaining = parse_existing_storage(db_path.read_bytes())
  assert len(remaining) == 1
  assert extract_dictionary_name(remaining[0]) == "ユーザー辞書 1"

