# VISA MCP Server

GitHub CopilotとVS CodeでVISA計測器を制御するためのMCPサーバーです。

## 概要

このサーバーは、実験室の計測器（電源、オシロスコープ、マルチメータなど）をGitHub Copilotから簡単に制御できるようにします。TCPIP、GPIB、USBなど様々な接続方式に対応しています。

## 必要なもの

- Python 3.11以上
- VISA ランタイム（NI-VISA、Keysight IO Librariesなど）
- VS Code with GitHub Copilot

## セットアップ

### 1. リポジトリのクローンと仮想環境の作成

```bash
git clone https://github.com/Hizuki1030/visa-mcp.git
cd visa-mcp

# 仮想環境を作成
python -m venv .venv

# 仮想環境を有効化
# macOS/Linux:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

# 依存関係をインストール
pip install -e .
```

### 2. 動作確認

```bash
# 仮想環境が有効化されていることを確認
python test_visa.py
```

### 3. VS Codeに登録

VS Codeの設定に以下を追加（仮想環境のPythonパスを指定）：

```json
{
  "servers": {
    "visa-mcp": {
      "command": "/path/to/visa-mcp/.venv/bin/python",
      "args": ["src/server.py"],
      "cwd": "/path/to/visa-mcp",
      "env": {
        "PYVISA_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

**注意**: `/path/to/visa-mcp`の部分は実際のプロジェクトパスに置き換えてください。
```

## 使い方

GitHub Copilotで「電源の電圧を5Vに設定して」のように自然な日本語で指示すると、適切なVISAコマンドが生成されます。

### 基本的な使用例

```python
# 機器の識別情報を取得
await send_visa_command("10.10.0.2", "inst0", "*IDN?")

# 電圧を設定
await send_visa_command("10.10.0.2", "inst0", "VOLT 5.0")

# 電圧を測定
await send_visa_command("10.10.0.3", "inst0", "MEAS:VOLT?")
```

## パラメータ

- `host`: 機器のIPアドレス
- `resource_id`: VISA リソース名（通常は "inst0"）
- `command`: SCPI/VISAコマンド
- `protocol`: 接続方式（"tcpip", "gpib", "usb"など）

## よくある問題

### VISA ランタイムが見つからない
```
Error: Could not locate a VISA implementation
```
→ NI-VISAやKeysight IO Librariesをインストールしてください

### 接続タイムアウト
```
VISA Error: VI_ERROR_TMO
```
→ IPアドレスと機器の電源を確認してください

### 詳細ログの有効化
```bash
export PYVISA_LOG_LEVEL=DEBUG
python src/server.py
```
```
