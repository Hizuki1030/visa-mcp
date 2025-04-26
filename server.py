# server.py
import time
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
import pyvisa

# Create an MCP server with debug enabled
mcp = FastMCP("VISA Oscilloscope Controller", debug=True)

# グローバル変数として接続されているオシロスコープを保持
oscilloscope = None

@mcp.tool()
def list_instruments() -> List[Dict[str, str]]:
    """利用可能なVISA機器の一覧を返します"""
    rm = pyvisa.ResourceManager()
    resources = rm.list_resources()
    result = []
    
    for res in resources:
        try:
            info = {"resource": res}
            # 機器の識別情報を取得（可能な場合）
            try:
                inst = rm.open_resource(res)
                # タイムアウトを設定（応答がない場合のハングを防止）
                inst.timeout = 1000  # 1秒
                try:
                    idn = inst.query("*IDN?")
                    info["idn"] = idn.strip()
                except Exception:
                    info["idn"] = "Unknown"
                inst.close()
            except Exception as e:
                info["idn"] = f"Error: {str(e)}"
            result.append(info)
        except Exception as e:
            result.append({"resource": res, "error": str(e)})
    
    return result

@mcp.tool()
def connect_oscilloscope(resource: str) -> Dict[str, Any]:
    """指定されたリソース識別子でオシロスコープに接続します"""
    global oscilloscope
    
    try:
        rm = pyvisa.ResourceManager()
        oscilloscope = rm.open_resource(resource)
        oscilloscope.timeout = 5000  # 5秒タイムアウト
        
        # 接続確認として機器IDを取得
        idn = oscilloscope.query("*IDN?")
        
        return {
            "status": "connected",
            "resource": resource,
            "idn": idn.strip()
        }
    except Exception as e:
        if oscilloscope is not None:
            try:
                oscilloscope.close()
            except:
                pass
        oscilloscope = None
        return {
            "status": "error",
            "message": str(e)
        }

@mcp.tool()
def disconnect_oscilloscope() -> Dict[str, str]:
    """オシロスコープの接続を切断します"""
    global oscilloscope
    
    if oscilloscope is None:
        return {"status": "not_connected"}
    
    try:
        oscilloscope.close()
        oscilloscope = None
        return {"status": "disconnected"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def get_oscilloscope_status() -> Dict[str, Any]:
    """オシロスコープの現在の状態を取得します"""
    global oscilloscope
    
    if oscilloscope is None:
        return {"status": "not_connected"}
    
    try:
        idn = oscilloscope.query("*IDN?")
        return {
            "status": "connected",
            "idn": idn.strip()
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def get_waveform(channel: int) -> Dict[str, Any]:
    """指定されたチャンネルの波形データを取得します"""
    global oscilloscope
    
    if oscilloscope is None:
        return {"status": "error", "message": "Not connected to oscilloscope"}
    
    try:
        # チャネル確認
        if not 1 <= channel <= 4:  # 多くのオシロはチャネル1〜4を持つ
            return {"status": "error", "message": f"Invalid channel: {channel}"}
        
        # 波形取得モードの設定
        oscilloscope.write(f":WAV:SOUR CHAN{channel}")
        oscilloscope.write(":WAV:FORM ASCII")
        
        # 水平軸情報の取得
        x_increment = float(oscilloscope.query(":WAV:XINC?"))
        x_origin = float(oscilloscope.query(":WAV:XOR?"))
        
        # 垂直軸情報の取得
        y_increment = float(oscilloscope.query(":WAV:YINC?"))
        y_origin = float(oscilloscope.query(":WAV:YOR?"))
        
        # 波形データの取得
        data_str = oscilloscope.query(":WAV:DATA?")
        # 多くのオシロは #9000012345などのヘッダーを返す
        # ヘッダーを除去してデータ部分だけを抽出
        if data_str.startswith("#"):
            header_length = int(data_str[1]) + 2  # #数字の後の長さ部分
            data_str = data_str[header_length:]
        
        # 文字列からデータポイントへの変換
        data_points = [float(x) for x in data_str.split(',')]
        
        # 時間軸の計算
        time_axis = [x_origin + i * x_increment for i in range(len(data_points))]
        
        # 電圧値の計算
        voltage_values = [(point - y_origin) * y_increment for point in data_points]
        
        return {
            "status": "success",
            "channel": channel,
            "time": time_axis[:100],  # データが多すぎる場合は最初の100ポイントだけを返す
            "voltage": voltage_values[:100],
            "points": len(data_points),
            "x_increment": x_increment,
            "y_increment": y_increment
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def set_timebase(scale: float) -> Dict[str, Any]:
    """オシロスコープのタイムベース（水平軸の時間スケール）を設定します
    
    Args:
        scale: 1目盛りあたりの秒数（例：1e-3は1ms/div）
    """
    global oscilloscope
    
    if oscilloscope is None:
        return {"status": "error", "message": "Not connected to oscilloscope"}
    
    try:
        oscilloscope.write(f":TIM:SCAL {scale}")
        actual_scale = float(oscilloscope.query(":TIM:SCAL?"))
        
        return {
            "status": "success",
            "requested_scale": scale,
            "actual_scale": actual_scale
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def set_channel_scale(channel: int, scale: float) -> Dict[str, Any]:
    """指定されたチャンネルの垂直スケール（電圧/div）を設定します
    
    Args:
        channel: チャンネル番号（1〜4）
        scale: 1目盛りあたりの電圧（例：0.1は100mV/div）
    """
    global oscilloscope
    
    if oscilloscope is None:
        return {"status": "error", "message": "Not connected to oscilloscope"}
    
    if not 1 <= channel <= 4:
        return {"status": "error", "message": f"Invalid channel: {channel}"}
    
    try:
        oscilloscope.write(f":CHAN{channel}:SCAL {scale}")
        actual_scale = float(oscilloscope.query(f":CHAN{channel}:SCAL?"))
        
        return {
            "status": "success",
            "channel": channel,
            "requested_scale": scale,
            "actual_scale": actual_scale
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def get_measurement(channel: int, measurement_type: str) -> Dict[str, Any]:
    """指定されたチャンネルの測定値を取得します
    
    Args:
        channel: チャンネル番号（1〜4）
        measurement_type: 測定タイプ（vpp, freq, period, duty, rise, fall, max, min, vamp, vtop, vbase）
    """
    global oscilloscope
    
    valid_measurements = [
        "vpp", "freq", "period", "duty", "rise", "fall", 
        "max", "min", "vamp", "vtop", "vbase"
    ]
    
    if oscilloscope is None:
        return {"status": "error", "message": "Not connected to oscilloscope"}
    
    if not 1 <= channel <= 4:
        return {"status": "error", "message": f"Invalid channel: {channel}"}
    
    if measurement_type.lower() not in valid_measurements:
        return {"status": "error", "message": f"Invalid measurement type: {measurement_type}"}
    
    try:
        # 測定項目をセットアップ（多くのオシロスコープに対応する共通コマンド）
        oscilloscope.write(f":MEAS:SOUR CHAN{channel}")
        oscilloscope.write(f":MEAS:{measurement_type.upper()}?")
        # 測定値を取得
        value = float(oscilloscope.query(f":MEAS:{measurement_type.upper()}?"))
        
        return {
            "status": "success",
            "channel": channel,
            "measurement": measurement_type,
            "value": value
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def send_command(command: str) -> Dict[str, Any]:
    """オシロスコープに任意のSCPIコマンドを送信します。
    クエリの場合は応答を返します。
    
    Args:
        command: 送信するSCPIコマンド
    """
    global oscilloscope
    
    if oscilloscope is None:
        return {"status": "error", "message": "Not connected to oscilloscope"}
    
    try:
        # クエリかどうかを判断（?で終わる）
        is_query = command.strip().endswith('?')
        
        if is_query:
            response = oscilloscope.query(command)
            return {
                "status": "success",
                "command": command,
                "response": response.strip()
            }
        else:
            oscilloscope.write(command)
            return {
                "status": "success",
                "command": command
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# 追加ユーティリティ
@mcp.tool()
def auto_scale() -> Dict[str, str]:
    """オシロスコープのオートスケール機能を実行します"""
    global oscilloscope
    
    if oscilloscope is None:
        return {"status": "error", "message": "Not connected to oscilloscope"}
    
    try:
        oscilloscope.write(":AUT")
        time.sleep(2)  # オートスケール実行の時間を確保
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# デモ用の加算ツールを維持
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

# Add this part to run the server
if __name__ == "__main__":
    # stdioトランスポートを使用
    print("Starting VISA Oscilloscope MCP Server in stdio mode")
    mcp.run(transport="stdio")