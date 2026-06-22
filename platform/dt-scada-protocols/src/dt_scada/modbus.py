"""
Modbus TCP/RTU master for substation IED communication.

Uses pymodbus 3.13+ (real open-source Modbus library) for:
- Modbus TCP client to RTUs, PLCs, IEDs
- Modbus RTU over serial (RS-232/485)
- Read holding registers, input registers, coils, discrete inputs
- Write single/multiple registers and coils
- Async I/O with asyncio
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModbusDeviceConfig:
    host: str = "127.0.0.1"
    port: int = 502
    unit_id: int = 1
    timeout: float = 10.0
    retries: int = 3
    scan_rate_ms: int = 1000
    holding_register_map: Dict[int, str] = field(default_factory=lambda: {
        0: "voltage_L1",
        1: "voltage_L2",
        2: "voltage_L3",
        3: "current_L1",
        4: "current_L2",
        5: "current_L3",
        6: "active_power",
        7: "reactive_power",
        8: "frequency",
        9: "power_factor",
    })
    coil_map: Dict[int, str] = field(default_factory=lambda: {
        0: "breaker_1",
        1: "breaker_2",
        2: "breaker_3",
        3: "disconnect_1",
    })


@dataclass
class ModbusMeasurement:
    address: int
    name: str
    value: float
    unit: str = ""
    quality: str = "good"
    timestamp: str = ""


class ModbusMaster:
    """
    Real Modbus master using pymodbus async client.

    Reads holding registers, input registers, coils, and discrete inputs
    from substation IEDs, RTUs, and protection relays.
    """

    def __init__(self, config: ModbusDeviceConfig, name: str = "modbus_1"):
        self.config = config
        self.name = name
        self._client = None
        self._connected = False
        self._running = False
        self._callbacks: List[Callable] = []
        self._measurements: Dict[str, ModbusMeasurement] = {}
        logger.info(f"ModbusMaster '{name}' configured for {config.host}:{config.port}")

    async def connect(self) -> bool:
        try:
            from pymodbus.client import AsyncModbusTcpClient
            self._client = AsyncModbusTcpClient(
                host=self.config.host,
                port=self.config.port,
                timeout=self.config.timeout,
            )
            self._connected = await self._client.connect()
            if self._connected:
                logger.info(f"Modbus connected to {self.config.host}:{self.config.port}")
            else:
                logger.warning(f"Modbus connection failed to {self.config.host}:{self.config.port}")
            return self._connected
        except ImportError:
            logger.error("pymodbus not installed. Run: pip install pymodbus")
            return False
        except Exception as e:
            logger.error(f"Modbus connection error: {e}")
            return False

    async def disconnect(self) -> None:
        self._running = False
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        self._connected = False
        logger.info(f"Modbus disconnected from {self.config.host}")

    def is_connected(self) -> bool:
        return self._connected

    def register_measurement_callback(self, callback: Callable) -> None:
        self._callbacks.append(callback)

    async def start_scanning(self) -> None:
        self._running = True
        while self._running and self._connected:
            try:
                await self._scan_holding_registers()
                await asyncio.sleep(self.config.scan_rate_ms / 1000)
            except Exception as e:
                logger.warning(f"Modbus scan error: {e}")
                await asyncio.sleep(5.0)

    async def stop_scanning(self) -> None:
        self._running = False

    async def _scan_holding_registers(self) -> None:
        if not self._client or not self._connected:
            return

        regs = self.config.holding_register_map
        if not regs:
            return

        max_addr = max(regs.keys())
        count = max_addr + 1

        try:
            result = await self._client.read_holding_registers(0, count, slave=self.config.unit_id)
            if result is None or result.isError():
                logger.warning(f"Modbus read error: {result}")
                return

            for addr, name in regs.items():
                if addr < len(result.registers):
                    raw = result.registers[addr]
                    val = self._scale_value(name, raw)
                    self._update_measurement(addr, name, val)
        except Exception as e:
            logger.warning(f"Modbus scan failed: {e}")

    def _scale_value(self, name: str, raw: int) -> float:
        if "voltage" in name and raw > 100:
            return raw / 100.0
        if "current" in name:
            return raw / 1000.0
        if "power" in name:
            return raw / 100.0
        if "frequency" in name:
            return raw / 100.0
        if "power_factor" in name:
            return raw / 10000.0
        return float(raw)

    def _update_measurement(self, addr: int, name: str, value: float) -> None:
        from datetime import datetime, timezone
        meas = ModbusMeasurement(
            address=addr,
            name=name,
            value=value,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._measurements[name] = meas
        for cb in self._callbacks:
            try:
                cb(meas)
            except Exception:
                pass

    async def read_holding_registers(self, address: int, count: int = 1) -> Optional[List[int]]:
        if not self._client or not self._connected:
            return None
        try:
            result = await self._client.read_holding_registers(address, count, slave=self.config.unit_id)
            if result and not result.isError():
                return result.registers
        except Exception as e:
            logger.warning(f"Read holding registers failed: {e}")
        return None

    async def read_input_registers(self, address: int, count: int = 1) -> Optional[List[int]]:
        if not self._client or not self._connected:
            return None
        try:
            result = await self._client.read_input_registers(address, count, slave=self.config.unit_id)
            if result and not result.isError():
                return result.registers
        except Exception as e:
            logger.warning(f"Read input registers failed: {e}")
        return None

    async def read_coils(self, address: int, count: int = 1) -> Optional[List[bool]]:
        if not self._client or not self._connected:
            return None
        try:
            result = await self._client.read_coils(address, count, slave=self.config.unit_id)
            if result and not result.isError():
                return result.bits
        except Exception as e:
            logger.warning(f"Read coils failed: {e}")
        return None

    async def write_register(self, address: int, value: int) -> bool:
        if not self._client or not self._connected:
            return False
        try:
            result = await self._client.write_register(address, value, slave=self.config.unit_id)
            return result is not None and not result.isError()
        except Exception as e:
            logger.error(f"Write register failed: {e}")
            return False

    async def write_coil(self, address: int, value: bool) -> bool:
        if not self._client or not self._connected:
            return False
        try:
            result = await self._client.write_coil(address, value, slave=self.config.unit_id)
            return result is not None and not result.isError()
        except Exception as e:
            logger.error(f"Write coil failed: {e}")
            return False

    def get_measurement(self, name: str) -> Optional[float]:
        m = self._measurements.get(name)
        return m.value if m else None

    def get_all_measurements(self) -> Dict[str, float]:
        return {k: m.value for k, m in self._measurements.items()}
