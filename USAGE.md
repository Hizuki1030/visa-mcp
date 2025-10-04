# VISA MCP Server 使用例

## 基本的な使用方法

### 1. VISA リソースの一覧表示

Copilot Chat で以下のように聞いてください：

```
利用可能なVISAリソースを一覧表示して
```

または：

```
list_visa_resources を実行して
```

### 2. 計測器への SCPI コマンド送信

#### 例1: 計測器のIDを取得
```
デバイス inst0 (192.168.0.50) に *IDN? を送って
```

#### 例2: オシロスコープの設定
```
send_visa_command を使って:
- host: 192.168.1.100
- resource_id: inst0 
- command: :CHANnel1:SCALe 0.1
```

#### 例3: 周波数測定
```
host: 192.168.1.100, resource_id: inst0 で MEAS:FREQ? を実行
```

### 3. プロトコルの指定

#### TCP/IP (VXI-11) - デフォルト
```
send_visa_command:
- host: 192.168.0.50
- resource_id: inst0
- protocol: tcpip
- command: *IDN?
```

#### Raw Socket
```
send_visa_command:
- host: 192.168.0.50
- resource_id: inst0
- protocol: socket
- port: 5025
- command: *IDN?
```

#### GPIB
```
send_visa_command:
- host: localhost
- resource_id: 2
- protocol: gpib
- command: *IDN?
```

### 4. タイムアウトと終端文字の設定

```
send_visa_command:
- host: 192.168.0.50
- resource_id: inst0
- command: *IDN?
- timeout_ms: 10000
- read_termination: "\r\n"
- write_termination: "\r\n"
```

## トラブルシューティング

### VISA Error: VI_ERROR_RSRC_NFOUND

リソース文字列を確認してください。正しい形式：
- TCP/IP: `TCPIP0::192.168.0.50::inst0::INSTR`
- GPIB: `GPIB0::2::INSTR`
- USB: `USB0::0x1234::0x5678::SERIAL::INSTR`

### タイムアウトエラー

1. `timeout_ms` を増加（デフォルト: 5000ms）
2. 終端文字を確認（`\n`, `\r\n`, `\r`）
3. ネットワーク接続を確認

### PyVISA ライブラリが見つからない

```bash
# PyVISA-Py（ソフトウェア実装）を使用
uv pip install pyvisa-py
```

## 実用例

### オシロスコープの自動測定

```
1. list_visa_resources でオシロスコープを確認
2. send_visa_command で *IDN? を送って接続確認
3. send_visa_command で :MEAS:FREQ? を送って周波数測定
4. send_visa_command で :MEAS:VAMP? を送って振幅測定
```

### ファンクションジェネレータの設定

```
1. send_visa_command: host=192.168.1.101, resource_id=inst0, command=*IDN?
2. send_visa_command: host=192.168.1.101, resource_id=inst0, command=:FREQ 1000
3. send_visa_command: host=192.168.1.101, resource_id=inst0, command=:VOLT 1.0
4. send_visa_command: host=192.168.1.101, resource_id=inst0, command=:OUTP ON
```

## 対応計測器例

- Keysight (Agilent) オシロスコープ
- Rohde & Schwarz スペクトラムアナライザ
- Tektronix 任意波形発生器
- Rigol デジタルマルチメータ
- その他 SCPI / IEEE-488 対応機器
