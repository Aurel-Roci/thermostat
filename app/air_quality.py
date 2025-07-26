import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from statistics import median, mean

logger = logging.getLogger(__name__)


class AirQualityAnalyzer:
    """Analyzes BME680 gas resistance using relative baseline approach"""

    def __init__(self, baseline_file: str = "/tmp/bme680_baseline.json"):
        self.baseline_file = baseline_file
        self.baseline_data = self._load_baseline()
        self.min_readings_for_baseline = 50  # Need 50+ readings for stable baseline
        self.baseline_window_hours = 72      # Use last 72 hours for baseline

    def _load_baseline(self) -> Dict:
        """Load existing baseline data"""
        try:
            if os.path.exists(self.baseline_file):
                with open(self.baseline_file, 'r') as f:
                    data = json.load(f)
                    logger.info(f"Loaded baseline data: {len(data.get('readings', []))} readings")
                    return data
        except Exception as e:
            logger.warning(f"Could not load baseline data: {e}")

        # Return empty baseline structure
        return {
            "readings": [],
            "baseline_value": None,
            "last_updated": None,
            "created": datetime.now().isoformat()
        }

    def _save_baseline(self):
        """Save baseline data to file"""
        try:
            with open(self.baseline_file, 'w') as f:
                json.dump(self.baseline_data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save baseline data: {e}")

    def add_reading(self, gas_resistance: float) -> Dict:
        """
        Add a new gas resistance reading and update baseline

        Args:
            gas_resistance: Raw gas resistance value from BME680

        Returns:
            Dict with air quality analysis
        """
        now = datetime.now()

        reading = {
            "value": gas_resistance,
            "timestamp": now.isoformat()
        }
        self.baseline_data["readings"].append(reading)

        # Keep only recent readings (last 72 hours)
        cutoff_time = now - timedelta(hours=self.baseline_window_hours)
        self.baseline_data["readings"] = [
            r for r in self.baseline_data["readings"]
            if datetime.fromisoformat(r["timestamp"]) > cutoff_time
        ]

        baseline_updated = self._update_baseline()

        analysis = self._analyze_reading(gas_resistance)

        self._save_baseline()

        return {
            **analysis,
            "baseline_updated": baseline_updated,
            "total_readings": len(self.baseline_data["readings"])
        }

    def _update_baseline(self) -> bool:
        """Update the baseline value using recent readings"""
        readings = self.baseline_data["readings"]

        if len(readings) < self.min_readings_for_baseline:
            return False

        # Use median of recent readings as baseline (more stable than mean)
        values = [r["value"] for r in readings]
        old_baseline = self.baseline_data["baseline_value"]
        new_baseline = median(values)

        self.baseline_data["baseline_value"] = new_baseline
        self.baseline_data["last_updated"] = datetime.now().isoformat()

        if old_baseline != new_baseline:
            logger.info(f"Baseline updated: {old_baseline} → {new_baseline}")
            return True

        return False

    def _analyze_reading(self, gas_resistance: float) -> Dict:
        """Analyze a reading against the baseline"""
        baseline = self.baseline_data["baseline_value"]

        if baseline is None:
            return {
                "gas_resistance": gas_resistance,
                "air_quality_status": "Learning",
                "air_quality_percentage": None,
                "air_quality_score": None,
                "description": f"Collecting baseline data ({len(self.baseline_data['readings'])}/{self.min_readings_for_baseline} readings)"
            }

        percentage = (gas_resistance / baseline) * 100

        # Convert to air quality score (0-100, where 100 is excellent)
        if percentage >= 100:
            score = min(100, 50 + (percentage - 100) * 0.5)  # Above baseline = good
        else:
            score = max(0, percentage * 0.5)  # Below baseline = poor

        status, description = self._get_air_quality_status(percentage, score)

        return {
            "gas_resistance": gas_resistance,
            "baseline_value": baseline,
            "air_quality_percentage": round(percentage, 1),
            "air_quality_score": round(score, 1),
            "air_quality_status": status,
            "description": description
        }

    def _get_air_quality_status(self, percentage: float, score: float) -> Tuple[str, str]:
        if score >= 85:
            return "Excellent", f"Air quality is {percentage:.0f}% of baseline - excellent conditions"
        elif score >= 70:
            return "Good", f"Air quality is {percentage:.0f}% of baseline - good conditions"
        elif score >= 50:
            return "Fair", f"Air quality is {percentage:.0f}% of baseline - acceptable conditions"
        elif score >= 30:
            return "Poor", f"Air quality is {percentage:.0f}% of baseline - poor conditions"
        else:
            return "Bad", f"Air quality is {percentage:.0f}% of baseline - very poor conditions"

    def get_baseline_info(self) -> Dict:
        """Get current baseline information"""
        return {
            "baseline_value": self.baseline_data["baseline_value"],
            "readings_count": len(self.baseline_data["readings"]),
            "last_updated": self.baseline_data["last_updated"],
            "baseline_ready": self.baseline_data["baseline_value"] is not None,
            "status": "Ready" if self.baseline_data["baseline_value"] else f"Learning ({len(self.baseline_data['readings'])}/{self.min_readings_for_baseline})"
        }
