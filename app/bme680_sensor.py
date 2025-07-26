import board
import adafruit_bme680
import time
import logging
from typing import Optional, Dict
from air_quality import AirQualityAnalyzer

logger = logging.getLogger(__name__)


class BME680Sensor:
    """BME680 sensor interface"""

    def __init__(self, db, device_id: str = "pi4_bme680"):
        self.db = db
        self.device_id = device_id
        self.sensor = None
        self._initialize_sensor()

    def _initialize_sensor(self):
        """Initialize the BME680 sensor"""
        try:
            i2c = board.I2C()
            self.sensor = adafruit_bme680.Adafruit_BME680_I2C(i2c)

            # Configure sensor settings
            self.sensor.sea_level_pressure = 1013.25

            logger.info("✅ BME680 sensor initialized successfully")

        except Exception as e:
            logger.error(f"❌ Failed to initialize BME680 sensor: {e}")
            self.sensor = None
            raise

    def read_sensor(self) -> Optional[Dict[str, float]]:
        """
        Read data from BME680 sensor

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

            # Round values for cleaner data
            readings = {
                'temperature': round(temperature, 2),
                'humidity': round(humidity, 2),
                'pressure': round(pressure, 2),
                'gas_resistance': round(gas, 0)
            }

            logger.debug(f"BME680 readings: {readings}")
            return readings

        except Exception as e:
            logger.error(f"❌ BME680 read error: {e}")
            return None

    def get_data(self, interval: int = 30):
        """
        Continuous sensor reading loop (like your original humidity.py)

        Args:
            interval: Time between readings in seconds
        """
        logger.info(f"🚀 Starting BME680 continuous reading (interval: {interval}s)")

        while True:
            try:
                readings = self.read_sensor()

                if readings:
                    # Send to database using new format
                    success = self.db.write_sensor_data(
                        device_id=self.device_id,
                        sensor_type="bme680",
                        **readings
                    )

                    if success:
                        logger.info(
                            f"📊 T={readings['temperature']}°C, "
                            f"H={readings['humidity']}%, "
                            f"P={readings['pressure']}hPa, "
                            f"Gas={readings['gas_resistance']}"
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
