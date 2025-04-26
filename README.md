# VISA-MCP: オシロスコープ制御ツール

VISA-MCPは、VISA（Virtual Instrument Software Architecture）を使用してオシロスコープなどの測定器を制御するためのMCP（Model-Command-Protocol）サーバーです。このツールを使用することで、さまざまなメーカーのオシロスコープをプログラムで簡単に制御できます。

## 主な機能

- **機器検出**: 接続されたVISA対応機器の自動検出と識別
- **波形取得**: チャンネルからの波形データの取得と解析
- **測定制御**: タイムベース、垂直スケール、トリガーなどの設定
- **測定値取得**: Vpp、周波数、立ち上がり時間などの自動測定
- **汎用コマンド**: 任意のSCPIコマンドをオシロスコープに送信可能

## 必要条件

- Python 3.13以上
- PyVISA
- PyVISA-py（バックエンド）
- MCPプロトコル対応クライアント

## インストール

```bash
# リポジトリをクローン
git clone https://github.com/Hizuki1030/visa-mcp.git
cd visa-mcp

# 依存関係をインストール
uv pip install -e .
```

## 使用方法

### MCPサーバーの設定

以下のような設定をMCPクライアントの設定ファイルに追加してください：

```json
{
"mcpServers": {
  "visa-oscilloscope": {
    "command": "/Users/user_name/.local/bin/uv",
    "args": [
      "--directory",
      "/Users/user_name/Documents/GitHub/visa-mcp",
      "run",
      "server.py"
    ],
    "alwaysAllow": [
      "list_instruments",
      "get_oscilloscope_status"
    ],
    "disabled": false
  }
}
}
```

※ uvコマンドのパスはフルパスで指定する必要があります。

### APIリファレンス

#### 機器接続管理

- `list_instruments()`: 利用可能なVISA機器の一覧を取得
- `connect_oscilloscope(resource)`: オシロスコープに接続
- `disconnect_oscilloscope()`: 接続を切断
- `get_oscilloscope_status()`: 接続状態を確認

#### 波形操作

- `get_waveform(channel)`: 指定チャンネルの波形データを取得
- `set_timebase(scale)`: 時間スケール設定
- `set_channel_scale(channel, scale)`: 垂直スケール設定
- `auto_scale()`: オートスケール実行

#### 測定機能

- `get_measurement(channel, measurement_type)`: 各種測定値の取得
  - 対応測定タイプ: vpp, freq, period, duty, rise, fall, max, min, vamp, vtop, vbase

#### 汎用制御

- `send_command(command)`: 任意のSCPIコマンドを送信

## ライセンス

MITライセンスの下で公開されています。

## 貢献

バグ報告や機能リクエストは、GitHubのIssueトラッカーを使用してください。プルリクエストも歓迎します。