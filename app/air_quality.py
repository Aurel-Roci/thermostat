import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from statistics import median, mean
import numpy as np

logger = logging.getLogger(__name__)


class AirQualityAnalyzer:
    """Analyzes BME680 gas resistance with optional fixed baseline"""

    def __init__(self, baseline_file: str = "/tmp/bme680_baseline.json"):
        self.baseline_file = baseline_file
        self.baseline_data = self._load_baseline()
        self.min_readings_for_baseline = 2880  # 24 hours at 30-second intervals
        self.baseline_window_hours = 72
        self.calibration_mode = True
        self.fixed_baseline_mode = False

    def _load_baseline(self) -> Dict:
        """Load existing baseline data"""
        try:
            if os.path.exists(self.baseline_file):
                with open(self.baseline_file, 'r') as f:
                    data = json.load(f)
                    logger.info(f"Loaded baseline data: {len(data.get('readings', []))} readings")

                    if data.get("fixed_baseline_mode", False):
                        self.fixed_baseline_mode = True
                        self.calibration_mode = False
                        logger.info(f"Operating in FIXED baseline mode: {data.get('baseline_value', 0):.0f}Ω")

                    return data
        except Exception as e:
            logger.warning(f"Could not load baseline data: {e}")

        return {
            "readings": [],
            "baseline_value": None,
            "baseline_std": None,
            "last_updated": None,
            "created": datetime.now().isoformat(),
            "calibration_complete": False,
            "fixed_baseline_mode": False,
            "fixed_baseline_timestamp": None
        }

    def _save_baseline(self):
        """Save baseline data to file"""
        try:
            with open(self.baseline_file, 'w') as f:
                json.dump(self.baseline_data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save baseline data: {e}")

    def add_reading(self, gas_resistance: float, temperature: float = None, humidity: float = None) -> Dict:
        """Add a new gas resistance reading and update baseline (unless fixed)"""
        now = datetime.now()

        reading = {
            "value": gas_resistance,
            "timestamp": now.isoformat(),
            "temperature": temperature,
            "humidity": humidity
        }

        # Always store the reading for historical purposes
        self.baseline_data["readings"].append(reading)

        # In fixed baseline mode, don't update baseline but still manage reading storage
        if self.fixed_baseline_mode:
            # Keep only recent readings for storage efficiency (but don't use for baseline)
            cutoff_time = now - timedelta(hours=24)  # Keep 24 hours for reference
            self.baseline_data["readings"] = [
                r for r in self.baseline_data["readings"]
                if datetime.fromisoformat(r["timestamp"]) > cutoff_time
            ]
            baseline_updated = False
        else:
            # Normal rolling window behavior during calibration
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
            "fixed_baseline_mode": self.fixed_baseline_mode
        }

    def _update_baseline(self) -> bool:
        """Update the baseline value (only if not in fixed mode)"""
        if self.fixed_baseline_mode:
            return False

        readings = self.baseline_data["readings"]

        if len(readings) < self.min_readings_for_baseline:
            return False

        values = [r["value"] for r in readings]
        baseline_75th = np.percentile(values, 75)
        baseline_std = np.std(values)

        old_baseline = self.baseline_data["baseline_value"]

        self.baseline_data["baseline_value"] = baseline_75th
        self.baseline_data["baseline_std"] = baseline_std
        self.baseline_data["last_updated"] = datetime.now().isoformat()

        # Mark calibration as complete if we have enough stable readings
        if len(readings) >= self.min_readings_for_baseline and baseline_std < (baseline_75th * 0.2):
            self.baseline_data["calibration_complete"] = True
            self.calibration_mode = False
            logger.info(f"Calibration complete! Baseline: {baseline_75th:.0f}, Std: {baseline_std:.0f}")

        if old_baseline != baseline_75th:
            logger.info(f"Baseline updated: {old_baseline} → {baseline_75th} (std: {baseline_std:.0f})")
            return True

        return False

    def _analyze_reading(self, gas_resistance: float) -> Dict:
        """Analyze a reading against the baseline"""
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

        if percentage >= 95:
            score = min(100, 70 + (percentage - 95) * 2)
        elif percentage >= 80:
            score = 50 + (percentage - 80) * (20/15)
        elif percentage >= 60:
            score = 30 + (percentage - 60) * (20/20)
        elif percentage >= 40:
            score = 15 + (percentage - 40) * (15/20)
        else:
            score = max(0, percentage * 0.375)

        status, description = self._get_air_quality_status(percentage, score)

        return {
            "gas_resistance": gas_resistance,
            "baseline_value": baseline,
            "baseline_std": baseline_std,
            "air_quality_percentage": round(percentage, 1),
            "air_quality_score": round(score, 1),
            "air_quality_status": status,
            "description": description,
            "calibration_mode": self.calibration_mode,
            "fixed_baseline_mode": self.fixed_baseline_mode
        }

    def _get_air_quality_status(self, percentage: float, score: float) -> Tuple[str, str]:
        """Get status with consideration for fixed baseline mode"""
        if self.calibration_mode:
            return "Calibrating", f"Still learning baseline - current reading is {percentage:.0f}% of provisional baseline"

        baseline_type = "fixed reference" if self.fixed_baseline_mode else "rolling baseline"

        if score >= 80:
            return "Excellent", f"Air quality is excellent ({percentage:.0f}% of {baseline_type})"
        elif score >= 65:
            return "Good", f"Air quality is good ({percentage:.0f}% of {baseline_type})"
        elif score >= 45:
            return "Moderate", f"Air quality is moderate ({percentage:.0f}% of {baseline_type})"
        elif score >= 25:
            return "Poor", f"Air quality is poor ({percentage:.0f}% of {baseline_type}) - consider ventilation"
        else:
            return "Very Poor", f"Air quality is very poor ({percentage:.0f}% of {baseline_type}) - ventilation needed!"

    def lock_baseline(self):
        """Lock the current baseline to prevent future updates"""
        if self.baseline_data["baseline_value"] is None:
            logger.warning("Cannot lock baseline - no baseline established yet")
            return False

        self.fixed_baseline_mode = True
        self.calibration_mode = False
        self.baseline_data["fixed_baseline_mode"] = True
        self.baseline_data["fixed_baseline_timestamp"] = datetime.now().isoformat()
        self.baseline_data["calibration_complete"] = True

        locked_value = self.baseline_data["baseline_value"]
        logger.info(f"🔒 Baseline LOCKED at {locked_value:.0f}Ω - will no longer update with new readings")

        self._save_baseline()
        return True

    def unlock_baseline(self):
        """Unlock the baseline to allow updates again"""
        self.fixed_baseline_mode = False
        self.baseline_data["fixed_baseline_mode"] = False
        self.baseline_data["fixed_baseline_timestamp"] = None

        logger.info("🔓 Baseline UNLOCKED - will resume updating with rolling window")
        self._save_baseline()

    def get_baseline_info(self) -> Dict:
        """Get current baseline information with fixed mode status"""
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
            "fixed_baseline_mode": self.fixed_baseline_mode,
            "fixed_baseline_timestamp": self.baseline_data.get("fixed_baseline_timestamp"),
            "baseline_ready": self.baseline_data["baseline_value"] is not None,
            "current_stats": current_stats,
            "stability": "Fixed" if self.fixed_baseline_mode else ("Stable" if current_stats.get("coefficient_of_variation", 100) < 20 else "Variable")
        }

    def reset_calibration(self):
        """Reset calibration - clears fixed baseline mode too"""
        logger.info("Resetting calibration data (including fixed baseline mode)")
        self.baseline_data = {
            "readings": [],
            "baseline_value": None,
            "baseline_std": None,
            "last_updated": None,
            "created": datetime.now().isoformat(),
            "calibration_complete": False,
            "fixed_baseline_mode": False,
            "fixed_baseline_timestamp": None
        }
        self.calibration_mode = True
        self.fixed_baseline_mode = False
        self._save_baseline()

    def force_calibration_complete(self):
        """Manually mark calibration as complete (but don't lock baseline)"""
        if self.baseline_data["baseline_value"] is not None:
            self.baseline_data["calibration_complete"] = True
            self.calibration_mode = False
            self._save_baseline()
            logger.info("Calibration manually marked as complete (baseline still updating)")
        else:
            logger.warning("Cannot complete calibration - no baseline established yet")
