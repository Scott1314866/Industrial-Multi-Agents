from __future__ import annotations

import math
import random
from datetime import UTC, datetime, timedelta

from industrial_agents.domain.models import MachineContext, TelemetryPoint

SCENARIOS: dict[str, dict[str, object]] = {
    "IMM-240A": {"model": "MOLDWISE MX-240", "fault": "normal_operation", "status": "running"},
    "IMM-320B": {"model": "MOLDWISE MX-320", "fault": "hydraulic_fault", "status": "warning"},
    "IMM-450C": {"model": "MOLDWISE MX-450", "fault": "product_defect", "status": "warning"},
    "IMM-550D": {"model": "MOLDWISE MX-550", "fault": "servo_fault", "status": "stopped"},
}


class SimulatedTelemetryGateway:
    """Deterministic industrial simulator derived from the eight-class fault corpus."""

    async def get_context(self, machine_id: str) -> MachineContext:
        scenario = SCENARIOS.get(machine_id, SCENARIOS["IMM-240A"])
        fault = str(scenario["fault"])
        rng = random.Random(f"moldwise:{machine_id}")
        end = datetime.now(UTC).replace(second=0, microsecond=0)
        points: list[TelemetryPoint] = []
        for index in range(30):
            phase = index / 4
            trend = index / 29
            oil_temp = 43 + math.sin(phase) * 1.2 + rng.uniform(-0.35, 0.35)
            pressure = 12.6 + math.sin(phase * 1.3) * 0.7 + rng.uniform(-0.25, 0.25)
            speed = 84 + math.sin(phase * 0.8) * 3 + rng.uniform(-1.2, 1.2)
            cycle = 31.8 + rng.uniform(-0.45, 0.45)
            servo = 61 + math.sin(phase) * 4 + rng.uniform(-1.5, 1.5)
            quality = 98.4 + rng.uniform(-0.5, 0.3)

            if fault == "hydraulic_fault":
                oil_temp += trend * 15
                pressure -= trend * 4.5
                cycle += trend * 3
            elif fault == "product_defect":
                pressure += math.sin(phase * 2.4) * 2.4
                cycle -= trend * 2.2
                quality -= trend * 8
            elif fault == "servo_fault":
                servo += trend * 34 + math.sin(phase * 2) * 7
                speed -= trend * 18
                cycle += trend * 5

            points.append(
                TelemetryPoint(
                    timestamp=end - timedelta(minutes=29 - index),
                    oil_temperature_c=round(oil_temp, 2),
                    injection_pressure_mpa=round(pressure, 2),
                    injection_speed_mm_s=round(speed, 2),
                    cycle_time_s=round(cycle, 2),
                    servo_load_pct=round(servo, 2),
                    quality_score=max(0, round(quality, 2)),
                )
            )

        alarms = {
            "hydraulic_fault": ["H-08"],
            "product_defect": ["Q-17"],
            "servo_fault": ["S-03", "E-05"],
        }.get(fault, [])
        return MachineContext(
            machine_id=machine_id,
            model=str(scenario["model"]),
            status=str(scenario["status"]),  # type: ignore[arg-type]
            alarm_codes=alarms,
            mold_cycles=184_220 + rng.randint(0, 12_000),
            active_batch=f"B-{end:%m%d}-{machine_id[-1]}",
            telemetry=points,
        )

    @staticmethod
    def list_machines() -> list[dict[str, object]]:
        return [
            {"id": machine_id, "name": f"{machine_id} · {item['model']}", "status": item["status"]}
            for machine_id, item in SCENARIOS.items()
        ]
