#!/usr/bin/env python3
"""
BME680 Pipeline for Pi 4
Main script for BME680 sensor data collection
"""

import os
import logging
from dotenv import load_dotenv
from app.database import VictoriaMetricsClient
from app.bme680_sensor import BME680Sensor

# Load environment variables
load_dotenv()

# Configuration
VM_HOST = os.getenv('VM_HOST', 'localhost')
VM_PORT = os.getenv('VM_PORT', '8428')
DEVICE_ID = os.getenv('DEVICE_ID', 'pi4_bme680')
READ_INTERVAL = int(os.getenv('READ_INTERVAL', '30'))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main pipeline function"""
    logger.info("🚀 Starting BME680 → VictoriaMetrics Pipeline")
    logger.info(f"📊 Target: {VM_HOST}:{VM_PORT}")
    logger.info(f"🔧 Device ID: {DEVICE_ID}")
    logger.info(f"⏱️ Read Interval: {READ_INTERVAL}s")

    try:
        # Initialize database client
        db = VictoriaMetricsClient(host=VM_HOST, port=VM_PORT)

        # Check database connectivity
        if not db.health_check():
            logger.warning("⚠️ VictoriaMetrics health check failed, but continuing...")

        # Initialize BME680 sensor
        sensor = BME680Sensor(db=db, device_id=DEVICE_ID)

        # Start continuous data collection
        sensor.get_data(interval=READ_INTERVAL)

    except KeyboardInterrupt:
        logger.info("🛑 Pipeline stopped by user")
    except Exception as e:
        logger.error(f"❌ Pipeline failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()
