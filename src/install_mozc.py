"""Linux Mozc (Fcitx5-mozc / IBus-mozc) ユーザー辞書への自動登録スクリプト。

既存の ~/.config/mozc/user_dictionary.db をバックアップした上で、
既存のユーザー辞書を保持したまま「地球科学」分野別辞書を追加・更新する。
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

from src.build_dict import FIELD_LABELS, DictEntry, deduplicate_entries, load_tsv

DICT_NAME_PREFIX = "地球科学（"
NOUN_POS_ENUM = 1  # mozc::user_dictionary::UserDictionary::NOUN


def encode_varint(value: int) -> bytes:
  """非負整数を Protocol Buffers の Varint 形式にエンコードする。"""
  if value < 0:
    raise ValueError("負の整数はエンコードできません")
  out = bytearray()
  while True:
    byte = value & 0x7F
    value >>= 7
    if value:
      out.append(byte | 0x80)
    else:
      out.append(byte)
      break
  return bytes(out)


def decode_varint(data: bytes, offset: int) -> tuple[int, int]:
  """Varint をデコードし、(値, 次のオフセット) を返す。"""
  result = 0
  shift = 0
  while offset < len(data):
    byte = data[offset]
    offset += 1
    result |= (byte & 0x7F) << shift
    if not (byte & 0x80):
      return result, offset
    shift += 7
  raise ValueError("Varint の途中でデータが終了しました")


def encode_length_delimited(field_number: int, payload: bytes) -> bytes:
  """Length-delimited フィールド (wire type = 2) をエンコードする。"""
  tag = (field_number << 3) | 2
  return encode_varint(tag) + encode_varint(len(payload)) + payload


def encode_varint_field(field_number: int, value: int) -> bytes:
  """Varint フィールド (wire type = 0) をエンコードする。"""
  tag = (field_number << 3) | 0
  return encode_varint(tag) + encode_varint(value)


def encode_entry(entry: DictEntry) -> bytes:
  """1つの辞書エントリを Mozc protobuf バイト列にエンコードする。"""
  parts = [
    encode_length_delimited(1, entry.reading.encode("utf-8")),
    encode_length_delimited(2, entry.word.encode("utf-8")),
  ]
  if entry.comment:
    parts.append(encode_length_delimited(4, entry.comment.encode("utf-8")))
  parts.append(encode_varint_field(5, NOUN_POS_ENUM))
  return b"".join(parts)


def make_dict_id(name: str) -> int:
  """辞書名から安定した64bit正整数のIDを生成する。"""
  digest = hashlib.sha256(name.encode("utf-8")).digest()
  # MSBを落として63bit正整数にする
  return int.from_bytes(digest[:8], "big") & 0x7FFFFFFFFFFFFFFF


def encode_user_dictionary(name: str, entries: list[DictEntry]) -> bytes:
  """1つの UserDictionary メッセージをエンコードする。"""
  dict_id = make_dict_id(name)
  parts = [
    encode_varint_field(1, dict_id),
    encode_length_delimited(3, name.encode("utf-8")),
  ]
  for entry in entries:
    parts.append(encode_length_delimited(4, encode_entry(entry)))
  return b"".join(parts)


def extract_dictionary_name(dict_bytes: bytes) -> str:
  """UserDictionary メッセージから field 3 (name) を抽出する。"""
  offset = 0
  while offset < len(dict_bytes):
    tag, offset = decode_varint(dict_bytes, offset)
    field_number = tag >> 3
    wire_type = tag & 0x07
    if wire_type == 0:
      _, offset = decode_varint(dict_bytes, offset)
    elif wire_type == 2:
      length, offset = decode_varint(dict_bytes, offset)
      payload = dict_bytes[offset : offset + length]
      offset += length
      if field_number == 3:
        return payload.decode("utf-8", errors="replace")
    elif wire_type == 1:
      offset += 8
    elif wire_type == 5:
      offset += 4
    else:
      raise ValueError(f"未対応の wire_type: {wire_type}")
  return ""


def parse_existing_storage(storage_bytes: bytes) -> list[bytes]:
  """既存の UserDictionaryStorage から、他のフィールドを除いた各 UserDictionary バイト列を抽出する。

  version などのトップレベルフィールドは保持せず、earth_science 以外の辞書ペイロードのみを返す。
  """
  other_dicts: list[bytes] = []
  offset = 0
  while offset < len(storage_bytes):
    tag, offset = decode_varint(storage_bytes, offset)
    field_number = tag >> 3
    wire_type = tag & 0x07
    if wire_type == 0:
      _, offset = decode_varint(storage_bytes, offset)
    elif wire_type == 2:
      length, offset = decode_varint(storage_bytes, offset)
      payload = storage_bytes[offset : offset + length]
      offset += length
      if field_number == 2:
        name = extract_dictionary_name(payload)
        if not name.startswith(DICT_NAME_PREFIX):
          other_dicts.append(payload)
    elif wire_type == 1:
      offset += 8
    elif wire_type == 5:
      offset += 4
    else:
      raise ValueError(f"未対応の wire_type: {wire_type}")
  return other_dicts


def install_to_mozc(base_dir: Path, db_path: Path) -> dict[str, int]:
  """Mozc の user_dictionary.db に地球科学辞書を登録する。"""
  db_path.parent.mkdir(parents=True, exist_ok=True)
  existing_dicts: list[bytes] = []

  if db_path.exists():
    backup_path = db_path.with_suffix(".db.bak")
    shutil.copy2(db_path, backup_path)
    existing_dicts = parse_existing_storage(db_path.read_bytes())

  new_storage_parts = [encode_length_delimited(2, d) for d in existing_dicts]
  counts: dict[str, int] = {}

  data_dir = base_dir / "data"
  for field_key, label in FIELD_LABELS.items():
    tsv_path = data_dir / f"{field_key}.tsv"
    entries = deduplicate_entries(load_tsv(tsv_path, field_key))
    dict_name = f"地球科学（{label}）"
    dict_payload = encode_user_dictionary(dict_name, entries)
    new_storage_parts.append(encode_length_delimited(2, dict_payload))
    counts[dict_name] = len(entries)

  db_path.write_bytes(b"".join(new_storage_parts))
  return counts


def reload_mozc_server() -> bool:
  """mozc_server プロセスを再起動して新しい辞書を即座に読み込ませる。"""
  res = subprocess.run(
    ["pkill", "-x", "mozc_server"],
    check=False,
    capture_output=True,
    text=True,
  )
  return res.returncode in (0, 1)


def main() -> None:
  """エントリーポイント。"""
  base_dir = Path(__file__).resolve().parent.parent
  db_path = Path.home() / ".config" / "mozc" / "user_dictionary.db"
  counts = install_to_mozc(base_dir, db_path)
  reload_mozc_server()
  print(f"Mozc ユーザー辞書 ({db_path}) に登録しました:")
  for name, count in counts.items():
    print(f"  - {name}: {count} 語")


if __name__ == "__main__":
  main()
