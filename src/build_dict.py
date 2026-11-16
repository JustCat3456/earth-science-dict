"""地球科学IMEユーザー辞書ビルダー

分野別TSVファイル（個体地球・大気海洋・宇宙）を読み込み、
全OS（Windows / macOS / Linux）および主要IME向けの辞書ファイルを生成する。
"""

from __future__ import annotations

import plistlib
import re
from dataclasses import dataclass
from pathlib import Path

# 読みとして許可する文字（ひらがな + 長音記号）
HIRAGANA_PATTERN = re.compile(r"^[ぁ-んー]+$")

FIELD_LABELS: dict[str, str] = {
  "solid_earth": "個体地球",
  "atmosphere_ocean": "大気海洋",
  "space_planetary": "宇宙",
}


@dataclass(frozen=True)
class DictEntry:
  """辞書の1エントリを表すデータクラス。"""

  reading: str
  word: str
  pos: str
  comment: str
  field: str


def validate_reading(reading: str) -> bool:
  """読みが純粋なひらがな・長音記号のみで構成されているか検証する。"""
  return bool(HIRAGANA_PATTERN.match(reading))


def load_tsv(file_path: Path, field_key: str) -> list[DictEntry]:
  """TSVファイルから辞書エントリを読み込む。"""
  entries: list[DictEntry] = []
  lines = file_path.read_text(encoding="utf-8").splitlines()

  for line_num, raw_line in enumerate(lines, start=1):
    line = raw_line.strip()
    if not line or line.startswith("#"):
      continue
    if line_num <= 5 and line.startswith("reading\tword"):
      continue

    parts = raw_line.split("\t")
    if len(parts) < 3:
      raise ValueError(
        f"{file_path.name}:{line_num} の列数が不足しています: {raw_line!r}"
      )

    reading = parts[0].strip()
    word = parts[1].strip()
    pos = parts[2].strip() or "名詞"
    comment = parts[3].strip() if len(parts) > 3 else ""

    if not validate_reading(reading):
      raise ValueError(
        f"{file_path.name}:{line_num} の読みにひらがな以外が含まれています: {reading!r}"
      )
    if not word:
      raise ValueError(f"{file_path.name}:{line_num} の単語が空です")

    entries.append(
      DictEntry(
        reading=reading,
        word=word,
        pos=pos,
        comment=comment,
        field=field_key,
      )
    )

  return entries


def deduplicate_entries(entries: list[DictEntry]) -> list[DictEntry]:
  """(reading, word) の完全重複を除去し、順序を維持する。"""
  seen: set[tuple[str, str]] = set()
  unique: list[DictEntry] = []
  for entry in entries:
    key = (entry.reading, entry.word)
    if key not in seen:
      seen.add(key)
      unique.append(entry)
  return unique


def write_google_mozc(entries: list[DictEntry], output_path: Path) -> None:
  """Google日本語入力 / Mozc (Windows / macOS / Linux) 向けTSVを出力する。"""
  output_path.parent.mkdir(parents=True, exist_ok=True)
  lines = [
    f"{e.reading}\t{e.word}\t{e.pos}\t{e.comment}" for e in entries
  ]
  output_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_windows_ms_ime(entries: list[DictEntry], output_path: Path) -> None:
  """Windows Microsoft IME 向けテキスト辞書 (UTF-16LE BOM付き, CRLF) を出力する。"""
  output_path.parent.mkdir(parents=True, exist_ok=True)
  lines = [
    f"{e.reading}\t{e.word}\t{e.pos}\t{e.comment}" for e in entries
  ]
  content = "\r\n".join(lines) + "\r\n"
  # utf-16 は先頭に BOM (FF FE) を付与してプラットフォーム依存エンディアンで書き出す
  # 明示的に UTF-16LE + BOM を出力するため encode("utf-16-le") に \ufeff を前置する
  raw_bytes = b"\xff\xfe" + content.encode("utf-16-le")
  output_path.write_bytes(raw_bytes)


def write_macos_plist(entries: list[DictEntry], output_path: Path) -> None:
  """macOS 日本語IM ユーザ辞書向け .plist ファイルを出力する。"""
  output_path.parent.mkdir(parents=True, exist_ok=True)
  plist_data = [
    {"phrase": e.word, "shortcut": e.reading} for e in entries
  ]
  with output_path.open("wb") as f:
    plistlib.dump(plist_data, f, fmt=plistlib.FMT_XML, sort_keys=True)


def write_glossary_markdown(
  entries_by_field: dict[str, list[DictEntry]], output_path: Path
) -> None:
  """人間が閲覧・検索しやすいMarkdown用語集を出力する。"""
  output_path.parent.mkdir(parents=True, exist_ok=True)
  lines: list[str] = [
    "# 地球科学 専門用語集",
    "",
    "IME辞書に収録されている用語の分野別一覧です。",
    "",
  ]
  for field_key, entries in entries_by_field.items():
    label = FIELD_LABELS.get(field_key, field_key)
    lines.append(f"## {label}（{len(entries)}語）")
    lines.append("")
    lines.append("| 単語 | 読み | 解説 |")
    lines.append("| :--- | :--- | :--- |")
    for e in entries:
      comment = e.comment.replace("|", "\\|")
      lines.append(f"| {e.word} | {e.reading} | {comment} |")
    lines.append("")

  output_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def build_all(base_dir: Path) -> dict[str, int]:
  """すべてのTSVを読み込み、各OS向けの辞書ファイルを生成する。"""
  data_dir = base_dir / "data"
  dist_dir = base_dir / "dist"

  entries_by_field: dict[str, list[DictEntry]] = {}
  all_entries: list[DictEntry] = []

  for field_key in FIELD_LABELS:
    tsv_path = data_dir / f"{field_key}.tsv"
    if not tsv_path.exists():
      raise FileNotFoundError(f"データファイルが見つかりません: {tsv_path}")
    field_entries = deduplicate_entries(load_tsv(tsv_path, field_key))
    entries_by_field[field_key] = field_entries
    all_entries.extend(field_entries)

  all_unique = deduplicate_entries(all_entries)

  # 分野別ファイル出力
  for field_key, entries in entries_by_field.items():
    write_google_mozc(
      entries, dist_dir / "google_mozc" / f"earth_science_{field_key}_mozc.txt"
    )
    write_windows_ms_ime(
      entries, dist_dir / "windows_ms_ime" / f"earth_science_{field_key}_msime.txt"
    )
    write_macos_plist(
      entries, dist_dir / "macos_ime" / f"earth_science_{field_key}_macos.plist"
    )

  # 全分野統合ファイル出力
  write_google_mozc(
    all_unique, dist_dir / "google_mozc" / "earth_science_all_mozc.txt"
  )
  write_windows_ms_ime(
    all_unique, dist_dir / "windows_ms_ime" / "earth_science_all_msime.txt"
  )
  write_macos_plist(
    all_unique, dist_dir / "macos_ime" / "earth_science_all_macos.plist"
  )

  # 用語集Markdown出力
  write_glossary_markdown(entries_by_field, dist_dir / "earth_science_glossary.md")

  counts = {k: len(v) for k, v in entries_by_field.items()}
  counts["all"] = len(all_unique)
  return counts


def main() -> None:
  """エントリーポイント。"""
  base_dir = Path(__file__).resolve().parent.parent
  counts = build_all(base_dir)
  print("地球科学IME辞書を生成しました:")
  for key, count in counts.items():
    label = FIELD_LABELS.get(key, "全分野統合")
    print(f"  - {label} ({key}): {count} 語")


if __name__ == "__main__":
  main()
