import board
import adafruit_bme680
import time
import logging
from typing import Optional, Dict
from .bsec_wrapper import BSECWrapper

logger = logging.getLogger(__name__)


class EnhancedBME680Sensor:
    """
    Enhanced BME680 sensor with BSEC air quality processing
    Uses Adafruit library for raw readings + BSEC for air quality
    """

    def __init__(self, db, device_id: str = "pi4_bme680", use_bsec: bool = True):
        self.db = db
        self.device_id = device_id
        self.sensor = None

        # Initialize BSEC wrapper
        self.bsec = BSECWrapper() if use_bsec else None
        self.bsec_available = False

        self._initialize_sensor()
        self._initialize_bsec()

    def _initialize_sensor(self):
        """Initialize the BME680 sensor using Adafruit library"""
        try:
            i2c = board.I2C()
            self.sensor = adafruit_bme680.Adafruit_BME680_I2C(i2c)
            self.sensor.sea_level_pressure = 1019

            logger.info("✅ BME680 sensor initialized successfully")

        except Exception as e:
            logger.error(f"❌ Failed to initialize BME680 sensor: {e}")
            self.sensor = None
            raise

    def _initialize_bsec(self):
        """Initialize BSEC for air quality processing"""
        if not self.bsec:
            logger.info("📊 BSEC disabled, using fallback air quality processing")
            return

        try:
            if self.bsec.initialize():
                self.bsec_available = True
                logger.info("🧠 BSEC initialized successfully for air quality processing")
                logger.info(f"BSEC Version: {self.bsec.get_version()}")
            else:
                logger.warning("⚠️ BSEC initialization failed, using fallback")
                self.bsec_available = False

        except Exception as e:
            logger.error(f"❌ BSEC initialization error: {e}")
            self.bsec_available = False

    def read_sensor(self) -> Optional[Dict[str, float]]:
        """
        Read data from BME680 sensor with optional BSEC processing
        """
        if not self.sensor:
            logger.error("❌ Sensor not initialized")
            return None

        try:
            temperature = self.sensor.temperature
            humidity = self.sensor.relative_humidity
            pressure = self.sensor.pressure
            gas = self.sensor.gas

            readings = {
                'temperature': round(temperature, 2),
                'humidity': round(humidity, 2),
                'pressure': round(pressure, 2),
                'gas_resistance': round(gas, 0),
            }

            if self.bsec_available:
                bsec_data = self.bsec.process_reading(temperature, humidity, pressure, gas)
                if bsec_data:
                    readings.update({
                        'iaq': round(bsec_data.get('iaq', 0), 1),
                        'iaq_accuracy': bsec_data.get('iaq_accuracy', 0),
                        'static_iaq': round(bsec_data.get('static_iaq', 0), 1),
                        'co2_equivalent': round(bsec_data.get('co2_equivalent', 0), 1),
                        'breath_voc_equivalent': round(bsec_data.get('breath_voc_equivalent', 0), 2),
                        'comp_gas_value': round(bsec_data.get('comp_gas_value', 0), 2),
                        'gas_percentage': round(bsec_data.get('gas_percentage', 0), 2)
                    })

                    # Add metadata for logging
                    readings['_processing_mode'] = 'bsec'
                    readings['_iaq_status'] = self._get_iaq_status(readings['iaq'])
                    readings['_accuracy_status'] = self._get_accuracy_status(readings['iaq_accuracy'])
                    readings['_calibration_complete'] = readings['iaq_accuracy'] >= 1

                    return readings

            readings['_processing_mode'] = 'raw_only'

            return readings

        except Exception as e:
            logger.error(f"❌ BME680 read error: {e}")
            return None

    def _get_iaq_status(self, iaq_value: float) -> str:
        """Convert IAQ value to descriptive status"""
        if iaq_value <= 50:
            return "Excellent"
        elif iaq_value <= 100:
            return "Good"
        elif iaq_value <= 150:
            return "Lightly Polluted"
        elif iaq_value <= 200:
            return "Moderately Polluted"
        elif iaq_value <= 250:
            return "Heavily Polluted"
        elif iaq_value <= 350:
            return "Severely Polluted"
        else:
            return "Extremely Polluted"

    def _get_accuracy_status(self, accuracy: int) -> str:
        """Convert accuracy level to descriptive status"""
        accuracy_map = {
            0: "Unreliable",
            1: "Low Accuracy",
            2: "Medium Accuracy",
            3: "High Accuracy"
        }
        return accuracy_map.get(accuracy, "Unknown")

    def get_data(self, interval: int = 30):
        """
        Continuous sensor reading loop with enhanced air quality

        Note: BSEC ULP mode works well with 30+ second intervals
        """
        logger.info(f"🚀 Starting Enhanced BME680 reading (interval: {interval}s)")

        if self.bsec_available:
            logger.info("🧠 Using BSEC for air quality processing (ULP mode)")
        else:
            logger.info("📊 Raw sensor readings only")

        reading_count = 0

        while True:
            try:
                readings = self.read_sensor()

                if readings:
                    # Prepare data for database (exclude metadata)
                    db_readings = {k: v for k, v in readings.items()
                                 if not k.startswith('_') and v is not None}

                    processing_mode = readings.get('_processing_mode', 'unknown')
                    sensor_type = f"bme680_{processing_mode}"

                    success = self.db.write_sensor_data(
                        device_id=self.device_id,
                        sensor_type=sensor_type,
                        **db_readings
                    )

                    if success:
                        reading_count += 1
                        self._log_reading(readings, reading_count)

                time.sleep(interval)

            except KeyboardInterrupt:
                logger.info("🛑 Enhanced BME680 sensor stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Unexpected error in get_data: {e}")
                time.sleep(5)

    def _log_reading(self, readings: Dict, count: int):
        """Log readings based on processing mode"""
        processing_mode = readings.get('_processing_mode', 'unknown')

        if processing_mode == 'bsec':
            iaq_status = readings.get('_iaq_status', 'Unknown')
            accuracy_status = readings.get('_accuracy_status', 'Unknown')
            accuracy = readings.get('iaq_accuracy', 0)

            if accuracy >= 1:  # At least low accuracy
                logger.info(
                    f"🧠 BSEC #{count}: T={readings['temperature']}°C, "
                    f"H={readings['humidity']}%, "
                    f"P={readings['pressure']}hPa, "
                    f"IAQ={readings['iaq']:.1f} ({iaq_status}), "
                    f"CO2eq={readings.get('co2_equivalent', 0):.0f}ppm, "
                    f"VOC={readings.get('breath_voc_equivalent', 0):.2f}ppm"
                )
            else:
                logger.info(
                    f"🔧 BSEC #{count} (Calibrating): T={readings['temperature']}°C, "
                    f"IAQ={readings['iaq']:.1f} ({accuracy_status}), "
                    f"Gas={readings['gas_resistance']:.0f}Ω"
                )
        else:
            logger.info(
                f"📊 Raw #{count}: T={readings['temperature']}°C, "
                f"H={readings['humidity']}%, "
                f"P={readings['pressure']}hPa, "
                f"Gas={readings['gas_resistance']:.0f}Ω"
            )

    def single_reading(self) -> Optional[Dict[str, float]]:
        """Get a single reading from the sensor"""
        return self.read_sensor()

    def get_status(self) -> Dict:
        """Get sensor and BSEC status"""
        status = {
            "sensor_initialized": self.sensor is not None,
            "bsec_available": self.bsec_available,
            "processing_mode": "bsec" if self.bsec_available else "fallback"
        }

        if self.bsec_available:
            status.update({
                "bsec_version": self.bsec.get_version(),
                "bsec_initialized": self.bsec.is_available()
            })

        return status

    def get_calibration_status(self) -> Dict:
        """Get calibration status"""
        readings = self.read_sensor()
        if not readings:
            return {"error": "Unable to read sensor"}

        processing_mode = readings.get('_processing_mode', 'unknown')

        if processing_mode == 'bsec':
            accuracy = readings.get('iaq_accuracy', 0)
            return {
                "mode": "bsec",
                "calibration_complete": accuracy >= 1,
                "accuracy_level": accuracy,
                "accuracy_status": self._get_accuracy_status(accuracy),
                "iaq_value": readings.get('iaq'),
                "iaq_status": self._get_iaq_status(readings.get('iaq', 0))
            }
        else:
            return {
                "mode": "raw_only",
                "calibration_complete": False
            }
