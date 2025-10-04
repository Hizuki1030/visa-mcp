"""
Modern VISA Manager for handling instrument connections and communication.
Supports serial ports, TCP/IP, and USB TMC connections with async/await pattern.
"""

import asyncio
import logging
import socket
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
from pathlib import Path

import pyvisa
import serial

logger = logging.getLogger(__name__)


class InterfaceType(Enum):
    """Supported interface types for VISA resources."""
    VISA = "VISA"
    SERIAL = "Serial"
    TCP_VISA = "TCP/IP-VISA"
    TCP_SOCKET = "TCP/IP-Socket"
    USB_TMC = "USB-TMC"


class ConnectionStatus(Enum):
    """Connection status states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class ResourceInfo:
    """Information about a discoverable VISA resource."""
    resource: str
    description: str
    interface_type: InterfaceType
    available: bool = True
    vendor_info: Optional[str] = None
    model_info: Optional[str] = None


@dataclass
class ConnectionInfo:
    """Information about an active connection."""
    resource: str
    interface_type: InterfaceType
    status: ConnectionStatus
    connected_at: float
    last_activity: float
    connection_object: Any
    error_message: Optional[str] = None
    connection_params: Dict[str, Any] = field(default_factory=dict)


class VISAError(Exception):
    """Custom exception for VISA-related errors."""
    pass


class VISAManager:
    """
    Modern async VISA manager for instrument connections and communication.
    
    Features:
    - Async/await pattern for non-blocking operations
    - Proper resource management with context managers
    - Comprehensive error handling and logging
    - Support for multiple interface types
    - Connection pooling and monitoring

    example : 
    ```
    {
  "host": "10.10.0.2",
  "resource_id": "1",
  "command": "*IDN?",
  "protocol": "tcpip",
  "read_termination": "\n",
  "write_termination": "\n",
  "timeout_ms": 5000
}
    ```
    """
    
    def __init__(self):
        self.connections: Dict[str, ConnectionInfo] = {}
        self.rm: Optional[pyvisa.ResourceManager] = None
        self._lock = asyncio.Lock()
        self._initialize_resource_manager()
    
    def _initialize_resource_manager(self) -> None:
        """Initialize PyVISA ResourceManager with proper error handling."""
        try:
            self.rm = pyvisa.ResourceManager()
            logger.info("PyVISA ResourceManager initialized successfully")
        except Exception as e:
            logger.warning(f"Could not initialize PyVISA ResourceManager: {e}")
            logger.info("Operating in limited mode without VISA support")
    
    async def list_resources(self) -> List[ResourceInfo]:
        """List all available VISA resources asynchronously."""
        async with self._lock:
            resources = []
            
            # Discover PyVISA resources
            await self._discover_visa_resources(resources)
            
            # Discover serial ports
            await self._discover_serial_ports(resources)
            
            # Add common TCP/IP examples
            self._add_tcp_examples(resources)
            
            logger.info(f"Found {len(resources)} resources")
            return resources
    
    async def _discover_visa_resources(self, resources: List[ResourceInfo]) -> None:
        """Discover available VISA resources."""
        if not self.rm:
            return
        
        try:
            # Run in thread pool to avoid blocking
            visa_resources = await asyncio.get_event_loop().run_in_executor(
                None, self.rm.list_resources
            )
            
            for resource in visa_resources:
                try:
                    # Try to get device identification
                    info = await self._get_resource_info(resource)
                    resources.append(info)
                except Exception as e:
                    logger.debug(f"Could not query resource {resource}: {e}")
                    resources.append(ResourceInfo(
                        resource=resource,
                        description="Unknown VISA device",
                        interface_type=InterfaceType.VISA,
                        available=True
                    ))
        except Exception as e:
            logger.warning(f"Could not list VISA resources: {e}")
    
    async def _get_resource_info(self, resource: str) -> ResourceInfo:
        """Get detailed information about a VISA resource."""
        def _query_resource():
            with self.rm.open_resource(resource) as instr:
                instr.timeout = 2000  # Short timeout for discovery
                return instr.query("*IDN?").strip()
        
        try:
            idn = await asyncio.get_event_loop().run_in_executor(None, _query_resource)
            return ResourceInfo(
                resource=resource,
                description=idn,
                interface_type=InterfaceType.VISA,
                available=True
            )
        except Exception:
            raise
    
    async def _discover_serial_ports(self, resources: List[ResourceInfo]) -> None:
        """Discover available serial ports."""
        try:
            import serial.tools.list_ports
            
            # Run in thread pool to avoid blocking
            ports = await asyncio.get_event_loop().run_in_executor(
                None, serial.tools.list_ports.comports
            )
            
            for port in ports:
                resources.append(ResourceInfo(
                    resource=port.device,
                    description=f"{port.description} - {port.manufacturer or 'Unknown'}",
                    interface_type=InterfaceType.SERIAL,
                    available=True,
                    vendor_info=port.manufacturer,
                    model_info=port.description
                ))
        except Exception as e:
            logger.warning(f"Could not list serial ports: {e}")
    
    def _add_tcp_examples(self, resources: List[ResourceInfo]) -> None:
        """Add common TCP/IP instrument addresses as examples."""
        tcp_examples = [
            ("TCPIP::192.168.1.100::INSTR", "TCP/IP Instrument (example)"),
            ("TCPIP::10.0.0.100::INSTR", "TCP/IP Instrument (example)"),
            ("TCPIP::localhost::5025::SOCKET", "TCP/IP Socket (example)")
        ]
        
        for address, description in tcp_examples:
            resources.append(ResourceInfo(
                resource=address,
                description=description,
                interface_type=InterfaceType.TCP_VISA,
                available=False
            ))
    
    @asynccontextmanager
    async def connect(
        self, 
        resource: str, 
        timeout: float = 5000,
        **kwargs
    ) -> AsyncGenerator[ConnectionInfo, None]:
        """
        Async context manager for connecting to a VISA resource.
        
        Usage:
            async with visa_manager.connect("COM3") as conn:
                await visa_manager.write(conn.resource, "*IDN?")
                response = await visa_manager.read(conn.resource)
        """
        async with self._lock:
            if resource in self.connections:
                raise VISAError(f"Already connected to {resource}")
            
            logger.info(f"Connecting to {resource}")
            conn_info = await self.establish_connection(resource, timeout, **kwargs)
            self.connections[resource] = conn_info
        
        try:
            logger.info(f"Successfully connected to {resource}")
            yield conn_info
        finally:
            async with self._lock:
                await self._cleanup_connection(resource)
    
    async def establish_connection(
        self, 
        resource: str, 
        timeout: float,
        **kwargs
    ) -> ConnectionInfo:
        """Establish connection based on resource type."""
        interface_type, connection_obj = await self._create_connection(
            resource, timeout, **kwargs
        )
        
        return ConnectionInfo(
            resource=resource,
            interface_type=interface_type,
            status=ConnectionStatus.CONNECTED,
            connected_at=time.time(),
            last_activity=time.time(),
            connection_object=connection_obj,
            connection_params=kwargs
        )
    
    async def _create_connection(
        self, 
        resource: str, 
        timeout: float,
        **kwargs
    ) -> tuple[InterfaceType, Any]:
        """Create appropriate connection object based on resource string."""
        
        if resource.startswith("TCPIP::") and resource.endswith("::SOCKET"):
            return await self._create_tcp_socket_connection(resource, timeout)
        elif resource.startswith("TCPIP::"):
            return await self._create_tcp_visa_connection(resource, timeout)
        elif resource.startswith(("COM", "/dev/")):
            return await self._create_serial_connection(resource, timeout, **kwargs)
        else:
            return await self._create_visa_connection(resource, timeout)
    
    async def _create_tcp_socket_connection(
        self, 
        resource: str, 
        timeout: float
    ) -> tuple[InterfaceType, socket.socket]:
        """Create raw TCP socket connection."""
        parts = resource.split("::")
        if len(parts) < 3:
            raise VISAError(f"Invalid TCP socket resource format: {resource}")
        
        host = parts[1]
        port = int(parts[2]) if parts[2].isdigit() else 5025
        
        def _connect_socket():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout / 1000.0)
            sock.connect((host, port))
            return sock
        
        try:
            sock = await asyncio.get_event_loop().run_in_executor(None, _connect_socket)
            return InterfaceType.TCP_SOCKET, sock
        except Exception as e:
            raise VISAError(f"Failed to connect to TCP socket {host}:{port}: {e}")
    
    async def _create_tcp_visa_connection(
        self, 
        resource: str, 
        timeout: float
    ) -> tuple[InterfaceType, Any]:
        """Create VISA TCP/IP connection."""
        if not self.rm:
            raise VISAError("No VISA resource manager available for TCP/IP connection")
        
        def _open_visa_resource():
            instr = self.rm.open_resource(resource)
            instr.timeout = timeout
            return instr
        
        try:
            instr = await asyncio.get_event_loop().run_in_executor(None, _open_visa_resource)
            return InterfaceType.TCP_VISA, instr
        except Exception as e:
            # Fallback to socket connection
            logger.warning(f"VISA TCP/IP failed, trying socket fallback: {e}")
            return await self._create_tcp_socket_connection(resource, timeout)
    
    async def _create_serial_connection(
        self, 
        resource: str, 
        timeout: float,
        **kwargs
    ) -> tuple[InterfaceType, serial.Serial]:
        """Create serial port connection."""
        serial_params = {
            'port': resource,
            'baudrate': kwargs.get('baudrate', 9600),
            'timeout': timeout / 1000.0,
            'parity': serial.PARITY_NONE,
            'stopbits': serial.STOPBITS_ONE,
            'bytesize': serial.EIGHTBITS,
            **kwargs
        }
        
        def _open_serial():
            return serial.Serial(**serial_params)
        
        try:
            ser = await asyncio.get_event_loop().run_in_executor(None, _open_serial)
            return InterfaceType.SERIAL, ser
        except Exception as e:
            raise VISAError(f"Failed to connect to serial port {resource}: {e}")
    
    async def _create_visa_connection(
        self, 
        resource: str, 
        timeout: float
    ) -> tuple[InterfaceType, Any]:
        """Create standard VISA connection."""
        if not self.rm:
            raise VISAError("No VISA resource manager available")
        
        def _open_visa_resource():
            instr = self.rm.open_resource(resource)
            instr.timeout = timeout
            return instr
        
        try:
            instr = await asyncio.get_event_loop().run_in_executor(None, _open_visa_resource)
            return InterfaceType.VISA, instr
        except Exception as e:
            raise VISAError(f"Failed to connect to VISA resource {resource}: {e}")
    
    async def _cleanup_connection(self, resource: str) -> None:
        """Clean up connection resources."""
        if resource not in self.connections:
            return
        
        conn_info = self.connections[resource]
        try:
            if hasattr(conn_info.connection_object, 'close'):
                await asyncio.get_event_loop().run_in_executor(
                    None, conn_info.connection_object.close
                )
            logger.info(f"Disconnected from {resource}")
        except Exception as e:
            logger.warning(f"Error closing connection to {resource}: {e}")
        finally:
            del self.connections[resource]
    
    async def write(self, resource: str, command: str) -> None:
        """Send a command to a connected VISA resource."""
        if resource not in self.connections:
            raise VISAError(f"Not connected to {resource}")
        
        conn_info = self.connections[resource]
        
        try:
            await self._write_to_connection(conn_info, command)
            conn_info.last_activity = time.time()
            logger.debug(f"Sent to {resource}: {command}")
        except Exception as e:
            conn_info.status = ConnectionStatus.ERROR
            conn_info.error_message = str(e)
            raise VISAError(f"Failed to write to {resource}: {e}")
    
    async def _write_to_connection(self, conn_info: ConnectionInfo, command: str) -> None:
        """Write command to connection based on interface type."""
        conn_obj = conn_info.connection_object
        
        if conn_info.interface_type == InterfaceType.SERIAL:
            data = command.encode()
            if not command.endswith('\n'):
                data += b'\n'
            await asyncio.get_event_loop().run_in_executor(None, conn_obj.write, data)
            
        elif conn_info.interface_type == InterfaceType.TCP_SOCKET:
            data = command.encode()
            if not command.endswith('\n'):
                data += b'\n'
            await asyncio.get_event_loop().run_in_executor(None, conn_obj.send, data)
            
        else:  # VISA connections
            await asyncio.get_event_loop().run_in_executor(None, conn_obj.write, command)
    
    async def read(self, resource: str, max_length: int = 1024) -> str:
        """Read data from a connected VISA resource."""
        if resource not in self.connections:
            raise VISAError(f"Not connected to {resource}")
        
        conn_info = self.connections[resource]
        
        try:
            data = await self._read_from_connection(conn_info, max_length)
            conn_info.last_activity = time.time()
            logger.debug(f"Received from {resource}: {data}")
            return data
        except Exception as e:
            conn_info.status = ConnectionStatus.ERROR
            conn_info.error_message = str(e)
            raise VISAError(f"Failed to read from {resource}: {e}")
    
    async def _read_from_connection(self, conn_info: ConnectionInfo, max_length: int) -> str:
        """Read data from connection based on interface type."""
        conn_obj = conn_info.connection_object
        
        if conn_info.interface_type == InterfaceType.SERIAL:
            data = await asyncio.get_event_loop().run_in_executor(
                None, conn_obj.readline
            )
            return data.decode().strip()
            
        elif conn_info.interface_type == InterfaceType.TCP_SOCKET:
            data = await asyncio.get_event_loop().run_in_executor(
                None, conn_obj.recv, max_length
            )
            return data.decode().strip()
            
        else:  # VISA connections
            data = await asyncio.get_event_loop().run_in_executor(
                None, conn_obj.read
            )
            return data.strip()
    
    async def query(
        self, 
        resource: str, 
        command: str, 
        timeout: Optional[float] = None
    ) -> str:
        """Send a command and read the response."""
        if resource not in self.connections:
            raise VISAError(f"Not connected to {resource}")
        
        conn_info = self.connections[resource]
        old_timeout = None
        
        # Temporarily change timeout if specified
        if timeout is not None:
            old_timeout = await self._set_timeout(conn_info, timeout)
        
        try:
            await self.write(resource, command)
            await asyncio.sleep(0.1)  # Small delay between write and read
            response = await self.read(resource)
            return response
        finally:
            if old_timeout is not None:
                await self._set_timeout(conn_info, old_timeout)
    
    async def _set_timeout(self, conn_info: ConnectionInfo, timeout: float) -> Optional[float]:
        """Set timeout for connection and return previous value."""
        conn_obj = conn_info.connection_object
        old_timeout = None
        
        if hasattr(conn_obj, 'timeout'):
            old_timeout = conn_obj.timeout
            if conn_info.interface_type in [InterfaceType.TCP_SOCKET, InterfaceType.SERIAL]:
                timeout_seconds = timeout / 1000.0
            else:
                timeout_seconds = timeout
            
            def _set_timeout():
                conn_obj.timeout = timeout_seconds
            
            await asyncio.get_event_loop().run_in_executor(None, _set_timeout)
        
        return old_timeout
    
    async def get_status(self, resource: Optional[str] = None) -> Dict[str, Any]:
        """Get connection status for all or specific resources."""
        if resource:
            if resource not in self.connections:
                return {"error": f"Not connected to {resource}"}
            
            conn_info = self.connections[resource]
            return {
                "resource": conn_info.resource,
                "interface_type": conn_info.interface_type.value,
                "status": conn_info.status.value,
                "connected_at": conn_info.connected_at,
                "last_activity": conn_info.last_activity,
                "uptime": time.time() - conn_info.connected_at,
                "error_message": conn_info.error_message,
                "connection_params": conn_info.connection_params
            }
        else:
            return {
                "total_connections": len(self.connections),
                "connections": {
                    res: {
                        "interface_type": info.interface_type.value,
                        "status": info.status.value,
                        "connected_at": info.connected_at,
                        "last_activity": info.last_activity,
                        "uptime": time.time() - info.connected_at,
                        "error_message": info.error_message
                    }
                    for res, info in self.connections.items()
                }
            }
    
    async def disconnect_all(self) -> None:
        """Disconnect from all resources."""
        resources = list(self.connections.keys())
        tasks = []
        
        for resource in resources:
            task = asyncio.create_task(self._cleanup_connection(resource))
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("Disconnected from all resources")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all connections."""
        health_status = {
            "healthy": True,
            "total_connections": len(self.connections),
            "connection_details": {},
            "errors": []
        }
        
        for resource, conn_info in self.connections.items():
            try:
                # Simple ping test for active connections
                if conn_info.status == ConnectionStatus.CONNECTED:
                    await self.query(resource, "*IDN?", timeout=1000)
                    health_status["connection_details"][resource] = "healthy"
            except Exception as e:
                health_status["healthy"] = False
                health_status["connection_details"][resource] = "unhealthy"
                health_status["errors"].append(f"{resource}: {str(e)}")
        
        return health_status
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect_all()


# Utility functions for common SCPI commands
class SCPICommands:
    """Common SCPI commands for different instrument types."""
    
    UNIVERSAL = [
        "*IDN?",  # Get instrument identification
        "*RST",   # Reset instrument
        "*CLS",   # Clear status
        "*ESR?",  # Event status register
        "*OPC?",  # Operation complete
        "SYST:ERR?",  # System error
    ]
    
    OSCILLOSCOPE = [
        "ACQ:MODE?",     # Acquisition mode
        "ACQ:SRAT?",     # Sample rate
        "CHAN1:SCAL?",   # Channel 1 scale
        "TIM:SCAL?",     # Timebase scale
        "MEAS:VMAX? CHAN1",  # Max voltage
        "MEAS:FREQ? CHAN1",  # Frequency
    ]
    
    FUNCTION_GENERATOR = [
        "OUTP:FREQ?",    # Output frequency
        "OUTP:AMPL?",    # Output amplitude
        "OUTP:FUNC?",    # Output function
        "OUTP:STAT?",    # Output state
    ]
    
    MULTIMETER = [
        "MEAS:VOLT:DC?", # DC voltage
        "MEAS:CURR:DC?", # DC current
        "MEAS:RES?",     # Resistance
        "CONF:VOLT:DC",  # Configure DC voltage
    ]
    
    POWER_SUPPLY = [
        "VOLT?",         # Voltage setting
        "CURR?",         # Current limit
        "OUTP?",         # Output state
        "MEAS:VOLT?",    # Actual voltage
        "MEAS:CURR?",    # Actual current
    ]
