# VISA MCP Server – FastMCP × PyVISA 実装ガイド
計測器のリモート制御で標準的に使われる **VISA** を、  
GitHub Copilot / VS Code の *MCP (Multi-Command Protocol)* から手軽に呼び出せるようにするサーバー実装と設定マニュアルです。

---

## 1. システム概要

```

┌─ VS Code / Copilot ─┐      stdio / http / sse      ┌──────── FastMCP Server ───────┐
│   (MCP Client)      │ ───────────────────────────▶ │ send\_visa\_command (PyVISA)    │
└─────────────────────┘                              └──────────┬───────────────────┘
│
▼
┌───── 計測器 (GPIB/LAN/USB) ────┐
│  SCPI / IEEE-488 / HiSLIP 等     │
└────────────────────────────────┘

````
---

## 2. MCP登録

```
{
  "servers": {
    "visaSender": {
      "type": "stdio",
      "command": "{install_path}/visa-mcp/.venv/bin/python3",
      "args": [
        "{install_path}/visa-mcp/src/server.py"
      ],
      "env": {
        "PYVISA_LOG_LEVEL": "INFO"
      }
    }
  }
}
```
