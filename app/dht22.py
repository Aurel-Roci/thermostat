import adafruit_dht as DHT
import board
import time
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# DHT22 Configuration
DHT_PIN = board.D4
DHT_SENSOR = DHT.DHT22(DHT_PIN, False)


class Sensor:
    """DHT22 sensor interface (keeping original class name for compatibility)"""

    def __init__(self, db, device_id: str = "pi2b_dht22"):
        self.db = db
        self.device_id = device_id
        logger.info(f"DHT22 sensor initialized for device: {device_id}")

    def read_sensor(self) -> Optional[Dict[str, float]]:
        """
        Read data from DHT22 sensor

        Returns:
            Dictionary with sensor readings or None if error
        """
        try:
            humidity = DHT_SENSOR.humidity
            temperature = DHT_SENSOR.temperature

            if humidity is not None and temperature is not None:
                readings = {
                    'temperature': round(temperature, 1),
                    'humidity': round(humidity, 1)
                }

                logger.debug(f"DHT22 readings: {readings}")
                return readings
            else:
                logger.warning("DHT22 returned None values")
                return None

        except RuntimeError as error:
            # DHT sensors are known to be finicky
            logger.warning(f"DHT22 read error: {error.args[0]}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected DHT22 error: {e}")
            return None

    def get_data(self, interval: float = 2.0):
        """
        Continuous sensor reading loop (original method, updated for VictoriaMetrics)

        Args:
            interval: Time between readings in seconds
        """
        logger.info(f"🚀 Starting DHT22 continuous reading (interval: {interval}s)")

        while True:
            try:
                readings = self.read_sensor()

                if readings:
                    # Send to VictoriaMetrics using new format
                    success = self.db.write_sensor_data(
                        device_id=self.device_id,
                        sensor_type="dht22",
                        **readings
                    )

                    if success:
                        logger.info(
                            f"📊 Temp={readings['temperature']:0.1f}°C   "
                            f"Humidity={readings['humidity']:0.1f}%"
                        )

                time.sleep(interval)

            except KeyboardInterrupt:
                logger.info("🛑 DHT22 sensor stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Unexpected error in get_data: {e}")
                time.sleep(2.0)  # Wait before retry

    def single_reading(self) -> Optional[Dict[str, float]]:
        """Get a single reading from the sensor"""
        return self.read_sensor()
