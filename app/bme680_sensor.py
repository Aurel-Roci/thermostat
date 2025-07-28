import board
import adafruit_bme680
import time
import logging
from typing import Optional, Dict
from .air_quality import AirQualityAnalyzer

logger = logging.getLogger(__name__)


class BME680Sensor:
    """BME680 sensor interface with improved air quality calibration"""

    def __init__(self, db, device_id: str = "pi4_bme680"):
        self.db = db
        self.device_id = device_id
        self.sensor = None
        self.air_quality = AirQualityAnalyzer()
        self._initialize_sensor()

    def _initialize_sensor(self):
        """Initialize the BME680 sensor"""
        try:
            i2c = board.I2C()
            self.sensor = adafruit_bme680.Adafruit_BME680_I2C(i2c)

            # Configure sensor settings
            self.sensor.sea_level_pressure = 1019

            logger.info("✅ BME680 sensor initialized successfully")

        except Exception as e:
            logger.error(f"❌ Failed to initialize BME680 sensor: {e}")
            self.sensor = None
            raise

    def read_sensor(self) -> Optional[Dict[str, float]]:
        """
        Read data from BME680 sensor with improved calibration

        Returns:
            Dictionary with sensor readings or None if error
        """
        if not self.sensor:
            logger.error("❌ Sensor not initialized")
            return None

        try:
            temperature = self.sensor.temperature
            humidity = self.sensor.relative_humidity
            pressure = self.sensor.pressure
            gas = self.sensor.gas

            # Pass temperature and humidity for potential compensation
            air_analysis = self.air_quality.add_reading(
                gas_resistance=gas,
                temperature=temperature,
                humidity=humidity
            )

            readings = {
                'temperature': round(temperature, 2),
                'humidity': round(humidity, 2),
                'pressure': round(pressure, 2),
                'gas_resistance': round(gas, 0),
                'air_quality_score': air_analysis.get('air_quality_score'),
                'air_quality_percentage': air_analysis.get('air_quality_percentage'),
                'baseline_value': air_analysis.get('baseline_value'),
                'baseline_std': air_analysis.get('baseline_std')
            }

            # Store metadata (not written to database)
            readings['_air_quality_status'] = air_analysis.get('air_quality_status', 'Unknown')
            readings['_air_quality_description'] = air_analysis.get('description', '')
            readings['_calibration_complete'] = air_analysis.get('calibration_complete', False)
            readings['_calibration_mode'] = air_analysis.get('calibration_mode', True)
            readings['_total_readings'] = air_analysis.get('total_readings', 0)

            logger.debug(f"BME680 readings: {readings}")
            return readings

        except Exception as e:
            logger.error(f"❌ BME680 read error: {e}")
            return None

    def get_data(self, interval: int = 30):
        """
        Continuous sensor reading loop with enhanced calibration logging

        Args:
            interval: Time between readings in seconds
        """
        logger.info(f"🚀 Starting BME680 continuous reading (interval: {interval}s)")

        # Log initial calibration status
        baseline_info = self.air_quality.get_baseline_info()
        if baseline_info['calibration_complete']:
            logger.info(f"📊 Using established baseline: {baseline_info['baseline_value']:.0f}")
        else:
            logger.info(f"🔧 Calibration in progress: {baseline_info['readings_count']}/{100} readings")

        reading_count = 0
        last_calibration_log = 0

        while True:
            try:
                readings = self.read_sensor()

                if readings:
                    # Prepare data for database (exclude metadata fields)
                    db_readings = {k: v for k, v in readings.items()
                                 if not k.startswith('_') and v is not None}

                    success = self.db.write_sensor_data(
                        device_id=self.device_id,
                        sensor_type="bme680",
                        **db_readings
                    )

                    if success:
                        reading_count += 1
                        status = readings.get('_air_quality_status', 'Unknown')
                        description = readings.get('_air_quality_description', '')
                        calibration_mode = readings.get('_calibration_mode', True)
                        total_readings = readings.get('_total_readings', 0)

                        # Enhanced logging based on calibration status
                        if calibration_mode:
                            # During calibration, log progress occasionally
                            if reading_count - last_calibration_log >= 10:  # Every 10 readings
                                baseline_info = self.air_quality.get_baseline_info()
                                stability = baseline_info.get('stability', 'Unknown')
                                logger.info(
                                    f"🔧 Calibrating: {total_readings}/100 readings, "
                                    f"Current: {readings['gas_resistance']:.0f}Ω, "
                                    f"Stability: {stability}, "
                                    f"AQ: {status}"
                                )
                                last_calibration_log = reading_count
                            else:
                                logger.debug(
                                    f"📊 T={readings['temperature']}°C, "
                                    f"H={readings['humidity']}%, "
                                    f"Gas={readings['gas_resistance']:.0f}Ω, "
                                    f"AQ={status} (calibrating)"
                                )
                        else:
                            # Normal operation logging
                            logger.info(
                                f"📊 T={readings['temperature']}°C, "
                                f"H={readings['humidity']}%, "
                                f"P={readings['pressure']}hPa, "
                                f"Gas={readings['gas_resistance']:.0f}Ω, "
                                f"AQ={status} ({readings.get('air_quality_score', 'N/A')}/100) - {description}"
                            )

                        # Log when calibration completes
                        if readings.get('_calibration_complete') and calibration_mode:
                            baseline_info = self.air_quality.get_baseline_info()
                            logger.info(
                                f"🎉 Calibration complete! "
                                f"Baseline: {baseline_info['baseline_value']:.0f}Ω, "
                                f"Stability: {baseline_info.get('stability', 'Unknown')}"
                            )

                time.sleep(interval)

            except KeyboardInterrupt:
                logger.info("🛑 BME680 sensor stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Unexpected error in get_data: {e}")
                time.sleep(5)  # Wait before retry

    def single_reading(self) -> Optional[Dict[str, float]]:
        """Get a single reading from the sensor"""
        return self.read_sensor()

    def get_calibration_status(self) -> Dict:
        """Get detailed calibration information"""
        baseline_info = self.air_quality.get_baseline_info()

        return {
            "calibration_complete": baseline_info.get('calibration_complete', False),
            "baseline_value": baseline_info.get('baseline_value'),
            "baseline_std": baseline_info.get('baseline_std'),
            "readings_count": baseline_info.get('readings_count', 0),
            "stability": baseline_info.get('stability', 'Unknown'),
            "current_stats": baseline_info.get('current_stats', {}),
            "last_updated": baseline_info.get('last_updated')
        }

    def reset_calibration(self):
        """Reset the air quality calibration"""
        logger.info("🔄 Resetting air quality calibration")
        self.air_quality.reset_calibration()

    def force_calibration_complete(self):
        """Manually mark calibration as complete"""
        logger.info("⚡ Forcing calibration completion")
        self.air_quality.force_calibration_complete()

    def log_calibration_diagnostics(self):
        """Log detailed calibration diagnostics"""
        baseline_info = self.air_quality.get_baseline_info()

        logger.info("📋 Air Quality Calibration Diagnostics:")
        logger.info(f"  Status: {'Complete' if baseline_info.get('calibration_complete') else 'In Progress'}")
        logger.info(f"  Readings: {baseline_info.get('readings_count', 0)}/{self.air_quality.min_readings_for_baseline}")
        logger.info(f"  Baseline: {baseline_info.get('baseline_value', 'Not set')}")
        logger.info(f"  Stability: {baseline_info.get('stability', 'Unknown')}")

        if baseline_info.get('current_stats'):
            stats = baseline_info['current_stats']
            logger.info(f"  Range: {stats.get('min', 0):.0f} - {stats.get('max', 0):.0f}Ω")
            logger.info(f"  Mean: {stats.get('mean', 0):.0f}Ω")
            logger.info(f"  Std Dev: {stats.get('std_dev', 0):.0f}Ω")
            logger.info(f"  Variability: {stats.get('coefficient_of_variation', 0):.1f}%")

    def lock_baseline(self):
        """Lock the current baseline to prevent future updates"""
        logger.info("🔒 Locking baseline to current value")
        success = self.air_quality.lock_baseline()
        if success:
            baseline_info = self.air_quality.get_baseline_info()
            logger.info(f"✅ Baseline locked at {baseline_info['baseline_value']:.0f}Ω")
        return success

    def unlock_baseline(self):
        """Unlock the baseline to allow updates again"""
        logger.info("🔓 Unlocking baseline for updates")
        self.air_quality.unlock_baseline()

    def get_baseline_lock_status(self) -> Dict:
        """Get baseline lock status"""
        baseline_info = self.air_quality.get_baseline_info()
        return {
            "is_locked": baseline_info.get('fixed_baseline_mode', False),
            "locked_timestamp": baseline_info.get('fixed_baseline_timestamp'),
            "baseline_value": baseline_info.get('baseline_value'),
            "stability": baseline_info.get('stability')
    }
