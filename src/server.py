#!/usr/bin/env python3
"""
VISA MCP Server - FastMCP × PyVISA implementation.

A Modern Model Context Protocol server for VISA instrument control
that integrates with GitHub Copilot / VS Code.

通常、電源は10.10.0.2、オシロスコープは10.10.0.3に接続されています

"""

from fastmcp import FastMCP, Context
import pyvisa
import asyncio
import aiohttp
import logging
import os

# Configure logging
log_level = os.getenv("PYVISA_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# -------- VISA 初期化 --------
rm = pyvisa.ResourceManager()  # DLL 自動検出 (NI-VISA / Keysight / RsVISA)

mcp = FastMCP("VISASender")

@mcp.tool
async def send_visa_command(
    host: str,
    resource_id: str,
    command: str,
    ctx: Context,
    port: int | None = None,
    protocol: str = "tcpip",
    read_termination: str = "\n",
    write_termination: str = "\n",
    timeout_ms: int = 5000,
) -> str:
    """
    Send a VISA/SCPI command to the target instrument.

    Args:
        host: IP or hostname of the instrument (e.g. 192.168.0.50).
        resource_id: Device name on visa side (e.g. inst0, gpib0,2).
        command: Raw SCPI/VISA command string (without terminator).
        port: Raw-socket mode only (default None → use VXI-11/HiSLIP).
        protocol: "tcpip" | "socket" | "gpib" | "usb" etc.
        read_termination / write_termination: Termination chars (LF default).
        timeout_ms: VISA timeout.
    Returns:
        Response string (query) or "OK" (write).
    """
    await ctx.info(f"Connecting to {host}/{resource_id} over {protocol.upper()}")

    # --- VISA Resource string build ---
    if protocol == "tcpip":
        visa_address = f"TCPIP0::{host}::{resource_id}::INSTR"
    elif protocol == "socket":
        visa_address = f"TCPIP0::{host}::{port or 5025}::SOCKET"
    elif protocol == "gpib":
        visa_address = f"GPIB0::{resource_id}::INSTR"
    elif protocol == "usb":
        visa_address = f"USB0::{resource_id}::INSTR"
    else:
        raise ValueError(f"Unsupported protocol: {protocol}")

    # --- Send command via PyVISA ---
    try:
        instr = rm.open_resource(
            visa_address,
            read_termination=read_termination,
            write_termination=write_termination,
            timeout=timeout_ms,
        )

        logger.info(f"Opened VISA resource: {visa_address}")
        
        if "?" in command.strip():
            result: str = instr.query(command)
            logger.info(f"Query '{command}' returned: {result.strip()}")
        else:
            instr.write(command)
            result = "OK"
            logger.info(f"Write command '{command}' executed successfully")

        instr.close()
        return result
        
    except pyvisa.Error as e:
        error_msg = f"VISA Error: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)


@mcp.tool
async def list_visa_resources(ctx: Context) -> str:
    """
    List all available VISA resources.

    Returns:
        A string containing all available VISA resources.
    """
    try:
        resources = rm.list_resources()
        if not resources:
            return "No VISA resources found"
        
        resource_list = "\n".join([f"- {res}" for res in resources])
        await ctx.info(f"Found {len(resources)} VISA resources")
        return f"Available VISA resources:\n{resource_list}"
        
    except Exception as e:
        error_msg = f"Error listing VISA resources: {e}"
        logger.error(error_msg)
        return error_msg


def main():
    """Entry point for the MCP server."""
    logger.info("Starting VISA MCP Server...")
    # stdio モードで起動。HTTP/SSE にしたい場合は transport 指定
    mcp.run()


if __name__ == "__main__":
    main()
