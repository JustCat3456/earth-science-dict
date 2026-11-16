# 地球科学 専門用語IME辞書（全OS対応）

地球科学を専攻する学生向けに、日本語IMEで一発変換しにくい専門用語をまとめたユーザー辞書セットです。
単語リストは**個体地球**、**大気海洋**、**宇宙**の3分野に分けて管理しています。

## ディレクトリ構成

- `data/`：分野別の元データ（TSV形式）
  - `solid_earth.tsv`：個体地球（地震学、地球内部構造、地質学、岩石、鉱物、地球化学）
  - `atmosphere_ocean.tsv`：大気海洋（大気力学、熱力学、気象、気候、海洋物理、海洋化学）
  - `space_planetary.tsv`：宇宙（太陽地球系、磁気圏、電離圏、惑星科学、天文学、宇宙論）
- `dist/`：各OS・IME向けに生成された辞書ファイル
  - `windows_ms_ime/`：Windows Microsoft IME 用（UTF-16LE BOM付き、CRLF）
  - `macos_ime/`：macOS 日本語IM ユーザ辞書用（`.plist`）
  - `google_mozc/`：Google日本語入力 / Mozc（Windows、macOS、Linux）用（UTF-8、LF）
  - `earth_science_glossary.md`：用語と解説の一覧表
- `src/build_dict.py`：TSVから全OS向け辞書を一括生成するスクリプト

## 各OSでのインポート方法

全分野をまとめて登録する場合は `*_all_*` を、特定分野だけ登録したい場合は分野別のファイルを使用してください。

### Windows（Microsoft IME）

1. タスクバー右下の「あ」または「A」を右クリックし、「ユーザー辞書ツール」を開きます。
2. メニューの「ツール」から「テキスト ファイルからの登録」を選択します。
3. `dist/windows_ms_ime/earth_science_all_msime.txt` を選択して登録します。

### macOS（標準日本語入力）

1. 「システム設定」から「キーボード」を開き、「ユーザ辞書...」をクリックします。
2. `dist/macos_ime/earth_science_all_macos.plist` をユーザ辞書のリスト画面へドラッグ＆ドロップします。

### Linux（Fcitx5-mozc / IBus-mozc）および Google日本語入力（Windows / macOS）

1. Mozc または Google日本語入力の「辞書ツール」を開きます。
2. 「管理」メニューから「新規辞書にインポート」（または既存の辞書にインポート）を選択します。
3. `dist/google_mozc/earth_science_all_mozc.txt` を選択し、文字コードを UTF-8、区切り文字をタブとして読み込みます。

### Android / iOS

- **Gboard（Android / iOS）**：Google日本語入力の辞書ツールでインポートした単語を同期するか、PCから単語リストをインポートできます。
- **iOS 標準キーボード**：macOS でユーザ辞書を登録すると、同じ Apple ID の iCloud 経由で iPhone / iPad にも自動的に同期されます。

## 単語の追加と再生成

`data/*.tsv` に `読み<TAB>単語<TAB>名詞<TAB>解説` の形式で追記したあと、以下のコマンドで全OS向けの辞書を再生成できます。

```bash
uv run python src/build_dict.py
```

テストの実行：

```bash
uv run pytest
```
