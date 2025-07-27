import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from statistics import median, mean
import numpy as np

logger = logging.getLogger(__name__)


class AirQualityAnalyzer:
    """Analyzes BME680 gas resistance using relative baseline approach"""

    def __init__(self, baseline_file: str = "/tmp/bme680_baseline.json"):
        self.baseline_file = baseline_file
        self.baseline_data = self._load_baseline()
        self.min_readings_for_baseline = 100  # Increased for more stability
        self.baseline_window_hours = 72
        self.calibration_mode = True  # Flag to indicate if still calibrating

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

        return {
            "readings": [],
            "baseline_value": None,
            "baseline_std": None,  # Added standard deviation tracking
            "last_updated": None,
            "created": datetime.now().isoformat(),
            "calibration_complete": False
        }

    def _save_baseline(self):
        """Save baseline data to file"""
        try:
            with open(self.baseline_file, 'w') as f:
                json.dump(self.baseline_data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save baseline data: {e}")

    def add_reading(self, gas_resistance: float, temperature: float = None, humidity: float = None) -> Dict:
        """
        Add a new gas resistance reading and update baseline

        Args:
            gas_resistance: Raw gas resistance value from BME680
            temperature: Temperature for compensation (optional)
            humidity: Humidity for compensation (optional)
        """
        now = datetime.now()

        reading = {
            "value": gas_resistance,
            "timestamp": now.isoformat(),
            "temperature": temperature,
            "humidity": humidity
        }
        self.baseline_data["readings"].append(reading)

        # Keep only recent readings
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
            "total_readings": len(self.baseline_data["readings"]),
            "calibration_complete": self.baseline_data.get("calibration_complete", False)
        }

    def _update_baseline(self) -> bool:
        """Update the baseline value using recent readings with stability check"""
        readings = self.baseline_data["readings"]

        if len(readings) < self.min_readings_for_baseline:
            return False

        values = [r["value"] for r in readings]

        # Use different percentiles to establish a more robust baseline
        baseline_25th = np.percentile(values, 25)
        baseline_median = np.percentile(values, 50)
        baseline_75th = np.percentile(values, 75)
        baseline_std = np.std(values)

        # Use 75th percentile as baseline (represents cleaner air conditions)
        # This assumes you'll have some periods of cleaner air in your 72-hour window
        new_baseline = baseline_75th

        old_baseline = self.baseline_data["baseline_value"]

        self.baseline_data["baseline_value"] = new_baseline
        self.baseline_data["baseline_std"] = baseline_std
        self.baseline_data["last_updated"] = datetime.now().isoformat()

        # Mark calibration as complete if we have enough stable readings
        if len(readings) >= self.min_readings_for_baseline and baseline_std < (new_baseline * 0.2):
            self.baseline_data["calibration_complete"] = True
            self.calibration_mode = False
            logger.info(f"Calibration complete! Baseline: {new_baseline:.0f}, Std: {baseline_std:.0f}")

        if old_baseline != new_baseline:
            logger.info(f"Baseline updated: {old_baseline} → {new_baseline} (std: {baseline_std:.0f})")
            return True

        return False

    def _analyze_reading(self, gas_resistance: float) -> Dict:
        """Analyze a reading against the baseline with improved scoring"""
        baseline = self.baseline_data["baseline_value"]
        baseline_std = self.baseline_data.get("baseline_std", 0)

        if baseline is None:
            return {
                "gas_resistance": gas_resistance,
                "air_quality_status": "Calibrating",
                "air_quality_percentage": None,
                "air_quality_score": None,
                "description": f"Collecting baseline data ({len(self.baseline_data['readings'])}/{self.min_readings_for_baseline} readings)"
            }

        # Calculate percentage relative to baseline
        percentage = (gas_resistance / baseline) * 100

        # Improved scoring algorithm
        if percentage >= 95:  # Within 5% of baseline or higher
            score = min(100, 70 + (percentage - 95) * 2)  # 70-100 range
        elif percentage >= 80:  # 80-95% of baseline
            score = 50 + (percentage - 80) * (20/15)  # 50-70 range
        elif percentage >= 60:  # 60-80% of baseline
            score = 30 + (percentage - 60) * (20/20)  # 30-50 range
        elif percentage >= 40:  # 40-60% of baseline
            score = 15 + (percentage - 40) * (15/20)  # 15-30 range
        else:  # Below 40% of baseline
            score = max(0, percentage * 0.375)  # 0-15 range

        status, description = self._get_air_quality_status(percentage, score)

        return {
            "gas_resistance": gas_resistance,
            "baseline_value": baseline,
            "baseline_std": baseline_std,
            "air_quality_percentage": round(percentage, 1),
            "air_quality_score": round(score, 1),
            "air_quality_status": status,
            "description": description,
            "calibration_mode": self.calibration_mode
        }

    def _get_air_quality_status(self, percentage: float, score: float) -> Tuple[str, str]:
        """Get status with more nuanced descriptions"""
        if self.calibration_mode:
            return "Calibrating", f"Still learning baseline - current reading is {percentage:.0f}% of provisional baseline"

        if score >= 80:
            return "Excellent", f"Air quality is excellent ({percentage:.0f}% of baseline)"
        elif score >= 65:
            return "Good", f"Air quality is good ({percentage:.0f}% of baseline)"
        elif score >= 45:
            return "Moderate", f"Air quality is moderate ({percentage:.0f}% of baseline)"
        elif score >= 25:
            return "Poor", f"Air quality is poor ({percentage:.0f}% of baseline)"
        else:
            return "Very Poor", f"Air quality is very poor ({percentage:.0f}% of baseline)"

    def get_baseline_info(self) -> Dict:
        """Get current baseline information with diagnostics"""
        readings = self.baseline_data["readings"]

        if len(readings) > 0:
            values = [r["value"] for r in readings]
            current_stats = {
                "min": min(values),
                "max": max(values),
                "mean": mean(values),
                "median": median(values),
                "std_dev": np.std(values) if len(values) > 1 else 0,
                "coefficient_of_variation": (np.std(values) / mean(values)) * 100 if len(values) > 1 and mean(values) > 0 else 0
            }
        else:
            current_stats = {}

        return {
            "baseline_value": self.baseline_data["baseline_value"],
            "baseline_std": self.baseline_data.get("baseline_std"),
            "readings_count": len(readings),
            "last_updated": self.baseline_data["last_updated"],
            "calibration_complete": self.baseline_data.get("calibration_complete", False),
            "baseline_ready": self.baseline_data["baseline_value"] is not None,
            "current_stats": current_stats,
            "stability": "Stable" if current_stats.get("coefficient_of_variation", 100) < 20 else "Variable"
        }

    def reset_calibration(self):
        """Reset calibration - use if you move to a different environment"""
        logger.info("Resetting calibration data")
        self.baseline_data = {
            "readings": [],
            "baseline_value": None,
            "baseline_std": None,
            "last_updated": None,
            "created": datetime.now().isoformat(),
            "calibration_complete": False
        }
        self.calibration_mode = True
        self._save_baseline()

    def force_calibration_complete(self):
        """Manually mark calibration as complete if you're confident in current baseline"""
        if self.baseline_data["baseline_value"] is not None:
            self.baseline_data["calibration_complete"] = True
            self.calibration_mode = False
            self._save_baseline()
            logger.info("Calibration manually marked as complete")
        else:
            logger.warning("Cannot complete calibration - no baseline established yet")
