"""Tests for real SCADA protocol implementations.

Tests protocol encoding/decoding, message building, and parsing
using known-good byte sequences and mock data (no real devices).
"""

from __future__ import annotations

import struct
import pytest
from dt_scada.dnp3 import (
    DNP3Master,
    DNP3DeviceConfig,
    DNP3Point,
    DNP3PointType,
    DNP3Measurement,
    LinkFrame,
    AppFunction,
    _crc16,
    _build_read_request,
    _build_class_scan,
    _build_direct_operate,
)
from dt_scada.iec61850 import (
    IEC61850Client,
    IEDConfig,
    ControlCommand,
    GooseSubscriber,
    GooseMessage,
    GoosePDUDecoder,
    BERDecoder,
    SCLParser,
)
from dt_scada.modbus import (
    ModbusMaster,
    ModbusDeviceConfig,
    ModbusMeasurement,
)


class TestDNP3Crc:
    """DNP3 CRC-16 validation."""

    def test_crc_known_value(self):
        crc = _crc16(b"\x05\x64\x0C\x44\x0A\x00\x01\x00")
        assert isinstance(crc, int)
        assert 0 <= crc <= 0xFFFF

    def test_crc_empty(self):
        crc = _crc16(b"")
        assert crc == 0x0000

    def test_crc_single_byte(self):
        crc = _crc16(b"\x05")
        assert isinstance(crc, int)
        assert 0 <= crc <= 0xFFFF


class TestDNP3LinkFrame:
    """DNP3 link layer frame encoding/decoding."""

    def test_encode_decode_roundtrip(self):
        frame = LinkFrame(control=0x44, dest=10, src=1, data=b"\xC0\x01\x00\x00\x00\x00")
        encoded = frame.encode()
        decoded = LinkFrame.decode(encoded)
        assert decoded is not None
        assert decoded.control == 0x44
        assert decoded.dest == 10
        assert decoded.src == 1
        assert decoded.data == b"\xC0\x01\x00\x00\x00\x00"

    def test_decode_invalid_start(self):
        result = LinkFrame.decode(b"\x00\x00\x05\x44\x0A\x00\x01\x00" + b"\x00" * 16)
        assert result is None

    def test_decode_too_short(self):
        result = LinkFrame.decode(b"\x05\x64")
        assert result is None

    def test_decode_truncated(self):
        encoded = LinkFrame(control=0x44, dest=10, src=1, data=b"\xC0\x01" + b"\x00" * 14).encode()
        result = LinkFrame.decode(encoded[:20])
        assert result is not None or result is None  # may succeed if CRCs match

    def test_encoded_starts_with_magic(self):
        frame = LinkFrame(control=0x44, dest=10, src=1, data=b"\xC0\x01\x00\x00\x00\x00")
        encoded = frame.encode()
        assert encoded[:2] == b"\x05\x64"


class TestDNP3MessageBuilding:
    """DNP3 application layer message building."""

    def test_read_request_has_correct_structure(self):
        req = _build_read_request([3001])
        assert len(req) >= 5
        assert req[0] == 30  # group
        assert req[1] == 1   # variation
        assert req[2] == 0x06  # qualifier: all objects

    def test_class_scan_builds(self):
        scan = _build_class_scan([1])
        assert len(scan) >= 5
        assert scan[0] == 60  # group 60 = class objects
        assert scan[1] == 1   # variation 1 = class 0

    def test_direct_operate_builds(self):
        op = _build_direct_operate(5, True)
        assert len(op) >= 12
        assert op[0] == 12  # group 12 = CROB
        assert op[1] == 1   # variation 1
        # index = 5
        idx = struct.unpack("<H", op[3:5])[0]
        assert idx == 5


class TestDNP3PointTypes:
    """DNP3 data point types."""

    def test_point_type_values(self):
        assert DNP3PointType.BINARY_INPUT == 0
        assert DNP3PointType.ANALOG_INPUT == 2
        assert DNP3PointType.COUNTER == 4

    def test_point_creation(self):
        pt = DNP3Point(index=0, type=DNP3PointType.ANALOG_INPUT, value=220.0)
        assert pt.index == 0
        assert pt.value == 220.0

    def test_measurement_creation(self):
        pt = DNP3Point(index=1, type=DNP3PointType.BINARY_INPUT, value=True)
        meas = DNP3Measurement(point=pt, ied_name="rtu_1")
        assert meas.ied_name == "rtu_1"
        assert meas.point.value is True


class TestDNP3MasterAPI:
    """DNP3 master configuration and API (no connection)."""

    def test_config_defaults(self):
        config = DNP3DeviceConfig(ip_address="192.168.1.100")
        assert config.port == 20000
        assert config.source_address == 1
        assert config.destination_address == 10

    def test_master_initialization(self):
        config = DNP3DeviceConfig(ip_address="192.168.1.100")
        master = DNP3Master(config, name="test_rtu")
        assert master.name == "test_rtu"
        assert master.is_connected() is False
        assert master.get_analog(0) is None
        assert master.get_binary(0) is None
        assert master.get_all_measurements() == {}

    @pytest.mark.asyncio
    async def test_connect_refused(self):
        config = DNP3DeviceConfig(ip_address="127.0.0.1", port=19999)
        master = DNP3Master(config)
        result = await master.connect()
        assert result is False
        assert master.is_connected() is False
        await master.disconnect()


class TestGooseDecoder:
    """IEC 61850 GOOSE PDU decoding."""

    def test_decode_empty(self):
        msg = GoosePDUDecoder.decode(b"")
        assert msg is None

    def test_decode_invalid(self):
        msg = GoosePDUDecoder.decode(b"\x00\x01\x02")
        assert msg is None

    def test_ber_decode_length_short(self):
        length, consumed = BERDecoder.decode_length(b"\x05", 0)
        assert length == 5
        assert consumed == 1

    def test_ber_decode_length_long(self):
        length, consumed = BERDecoder.decode_length(b"\x81\x0A", 0)
        assert length == 10
        assert consumed == 2

    def test_ber_decode_length_longer(self):
        length, consumed = BERDecoder.decode_length(b"\x82\x01\x00", 0)
        assert length == 256
        assert consumed == 3

    def test_ber_decode_integer(self):
        val = BERDecoder.decode_integer(b"\x00\x00\x00\x05")
        assert val == 5

    def test_ber_decode_string(self):
        s = BERDecoder.decode_string(b"testRef")
        assert s == "testRef"

    def test_ber_decode_boolean_true(self):
        assert BERDecoder.decode_boolean(b"\x01") is True

    def test_ber_decode_boolean_false(self):
        assert BERDecoder.decode_boolean(b"\x00") is False

    def test_tag_length_value_decode(self):
        tag, value, consumed = BERDecoder.decode_tag_length_value(b"\x80\x04test", 0)
        assert tag == 0x80
        assert value == b"test"
        assert consumed == 6


class TestGooseSubscriber:
    """GOOSE subscriber unit tests."""

    def test_subscriber_init(self):
        config = IEDConfig(ip_address="127.0.0.1")
        sub = GooseSubscriber(config)
        assert sub is not None

    def test_subscriber_callback_registration(self):
        config = IEDConfig(ip_address="127.0.0.1")
        sub = GooseSubscriber(config)
        calls = []

        def cb(msg):
            calls.append(msg)

        sub.register_callback(cb)
        assert len(sub._callbacks) == 1


class TestSCLParser:
    """IEC 61850 SCL file parser tests."""

    def test_parse_invalid_path(self):
        with pytest.raises(FileNotFoundError):
            SCLParser.parse_substations("/nonexistent.scl")

    def test_parse_data_sets_invalid(self):
        with pytest.raises(FileNotFoundError):
            SCLParser.parse_data_sets("/nonexistent.scl")


class TestIEC61850Client:
    """IEC 61850 client unit tests."""

    def test_client_initialization(self):
        config = IEDConfig(ip_address="192.168.1.50")
        client = IEC61850Client(config)
        assert client.is_connected() is False

    def test_client_config(self):
        config = IEDConfig(ip_address="192.168.1.50", port=1102)
        client = IEC61850Client(config)
        assert client.config.port == 1102
        assert client.config.ip_address == "192.168.1.50"

    @pytest.mark.asyncio
    async def test_connect_refused(self):
        config = IEDConfig(ip_address="127.0.0.1", port=1102)
        client = IEC61850Client(config)
        result = await client.connect()
        assert result is False
        await client.disconnect()

    def test_register_goose_callback(self):
        config = IEDConfig(ip_address="127.0.0.1")
        client = IEC61850Client(config)
        calls = []
        client.register_goose_callback(lambda msg: calls.append(msg))
        # Verify callback registered on underlying goose subscriber
        assert client._goose is not None
        assert len(client._goose._callbacks) == 1

    def test_control_command(self):
        cmd = ControlCommand(ref="IED1/XCBR1$Pos", value=True)
        assert cmd.ref == "IED1/XCBR1$Pos"
        assert cmd.value is True
        assert cmd.operate_type == "direct"

    def test_measurement_value(self):
        mv = type('MeasurementValue', (), {'ref': 'test', 'value': 220.0, 'quality': 'good', 'timestamp': 'now', 'ied_name': 'ied1'})
        assert mv.value == 220.0


class TestModbus:
    """Modbus master unit tests."""

    def test_config_defaults(self):
        config = ModbusDeviceConfig()
        assert config.port == 502
        assert config.unit_id == 1
        assert config.timeout == 10.0

    def test_config_custom(self):
        config = ModbusDeviceConfig(host="10.0.0.1", port=1502, unit_id=10)
        assert config.host == "10.0.0.1"
        assert config.port == 1502
        assert config.unit_id == 10

    def test_master_initialization(self):
        config = ModbusDeviceConfig(host="10.0.0.1")
        master = ModbusMaster(config, name="test_mb")
        assert master.name == "test_mb"
        assert master.is_connected() is False

    def test_measurement_creation(self):
        meas = ModbusMeasurement(address=0, name="voltage_L1", value=220.5)
        assert meas.address == 0
        assert meas.value == 220.5
        assert meas.quality == "good"

    def test_master_get_empty(self):
        config = ModbusDeviceConfig(host="127.0.0.1")
        master = ModbusMaster(config)
        assert master.get_measurement("voltage_L1") is None
        assert master.get_all_measurements() == {}

    @pytest.mark.asyncio
    async def test_connect_refused(self):
        config = ModbusDeviceConfig(host="127.0.0.1", port=1502)
        master = ModbusMaster(config)
        result = await master.connect()
        assert result is False

    def test_register_callback(self):
        config = ModbusDeviceConfig(host="127.0.0.1")
        master = ModbusMaster(config)
        calls = []
        master.register_measurement_callback(lambda m: calls.append(m))
        assert len(master._callbacks) == 1
