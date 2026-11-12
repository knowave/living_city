"""이벤트·스냅샷·청크·지표 레코드 테스트."""

import unittest
import uuid
from decimal import Decimal

from simulation_engine.events.models import WorldEvent
from simulation_engine.metrics.models import MetricCode, MetricPeriod, MetricUnit, WorldMetric
from simulation_engine.world.map_chunk import CHUNK_SIZE, MapChunk
from simulation_engine.world.snapshot import WorldSnapshot


class WorldEventTest(unittest.TestCase):
    def test_defaults(self):
        event = WorldEvent(id=uuid.uuid4(), sequence=1, tick=0, type="TICK")
        self.assertEqual(event.payload, {})
        self.assertEqual(event.schema_version, 1)

    def test_payload_is_not_shared_between_instances(self):
        a = WorldEvent(id=uuid.uuid4(), sequence=1, tick=0, type="TICK")
        b = WorldEvent(id=uuid.uuid4(), sequence=2, tick=0, type="TICK")
        a.payload["k"] = "v"
        self.assertEqual(b.payload, {})


class WorldSnapshotTest(unittest.TestCase):
    def test_defaults(self):
        snap = WorldSnapshot(id=uuid.uuid4(), tick=10, last_event_sequence=5, engine_version="0.1.0")
        self.assertEqual(snap.state_data, {})
        self.assertEqual(snap.tick, 10)

    def test_state_data_is_not_shared_between_instances(self):
        a = WorldSnapshot(id=uuid.uuid4(), tick=1, last_event_sequence=0, engine_version="0.1.0")
        b = WorldSnapshot(id=uuid.uuid4(), tick=2, last_event_sequence=0, engine_version="0.1.0")
        a.state_data["k"] = 1
        self.assertEqual(b.state_data, {})


class MapChunkTest(unittest.TestCase):
    def test_chunk_size_constant(self):
        self.assertEqual(CHUNK_SIZE, 32)

    def test_defaults(self):
        chunk = MapChunk(id=uuid.uuid4(), chunk_x=0, chunk_y=1, terrain_tiles=[0] * 1024, road_tiles=[0] * 1024)
        self.assertEqual(chunk.chunk_size, CHUNK_SIZE)
        self.assertEqual(chunk.schema_version, 1)
        self.assertEqual(chunk.revision, 1)
        self.assertEqual(len(chunk.terrain_tiles), 1024)


class MetricEnumTest(unittest.TestCase):
    def test_metric_code_values_match_backend(self):
        self.assertEqual(
            [m.value for m in MetricCode],
            [
                "POPULATION",
                "EMPLOYED_POPULATION",
                "UNEMPLOYMENT_RATE",
                "AVERAGE_SALARY",
                "AVERAGE_WEALTH",
                "TOTAL_CONSUMPTION",
                "TOTAL_COMPANY_REVENUE",
                "ACTIVE_COMPANIES",
                "BANKRUPT_COMPANIES",
                "GOVERNMENT_REVENUE",
                "GOVERNMENT_EXPENDITURE",
                "AVERAGE_HAPPINESS",
            ],
        )

    def test_unit_values_match_backend(self):
        self.assertEqual([u.value for u in MetricUnit], ["COUNT", "KRW", "PERCENT", "RATIO", "INDEX"])

    def test_period_values_match_backend(self):
        self.assertEqual([p.value for p in MetricPeriod], ["HOURLY", "DAILY", "MONTHLY"])


class WorldMetricTest(unittest.TestCase):
    def test_defaults_and_fields(self):
        metric = WorldMetric(
            id=uuid.uuid4(),
            tick=100,
            metric_code=MetricCode.POPULATION,
            metric_value=Decimal("1234.000000"),
            unit=MetricUnit.COUNT,
            period=MetricPeriod.DAILY,
        )
        self.assertEqual(metric.definition_version, 1)
        self.assertEqual(metric.metric_value, Decimal("1234.000000"))
        self.assertEqual(metric.metric_code, "POPULATION")


if __name__ == "__main__":
    unittest.main()
