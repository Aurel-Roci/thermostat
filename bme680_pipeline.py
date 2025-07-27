import os
import sys
import logging
import argparse
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


def setup_argument_parser():
    """Setup command line argument parser"""
    parser = argparse.ArgumentParser(description='BME680 → VictoriaMetrics Pipeline')
    parser.add_argument('--reset-calibration', action='store_true',
                       help='Reset air quality calibration and start fresh')
    parser.add_argument('--force-complete-calibration', action='store_true',
                       help='Mark current calibration as complete')
    parser.add_argument('--show-calibration-status', action='store_true',
                       help='Show current calibration status and exit')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    return parser


def main():
    """Main pipeline function with calibration management"""

    # Parse command line arguments
    parser = setup_argument_parser()
    args = parser.parse_args()

    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("🐛 Debug logging enabled")

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

        # Handle calibration management commands
        if args.reset_calibration:
            logger.info("🔄 Resetting air quality calibration...")
            sensor.reset_calibration()
            logger.info("✅ Calibration reset complete")
            return

        if args.force_complete_calibration:
            logger.info("⚡ Forcing calibration completion...")
            sensor.force_calibration_complete()
            status = sensor.get_calibration_status()
            if status['calibration_complete']:
                logger.info("✅ Calibration marked as complete")
            else:
                logger.warning("⚠️ Could not complete calibration - no baseline established yet")
            return

        if args.show_calibration_status:
            logger.info("📋 Current Calibration Status:")
            sensor.log_calibration_diagnostics()
            return

        # Show initial calibration status
        status = sensor.get_calibration_status()
        if status['calibration_complete']:
            logger.info(f"✅ Using established baseline: {status['baseline_value']:.0f}Ω")
            logger.info(f"📊 Stability: {status['stability']}")
        else:
            logger.info(f"🔧 Calibration in progress: {status['readings_count']}/100 readings")
            logger.info("💡 Tip: Place sensor in clean air for best baseline establishment")

            # Show some guidance for calibration
            if status['readings_count'] == 0:
                logger.info("🏁 Starting fresh calibration - let it run for 24-72 hours")
            elif status['readings_count'] < 50:
                logger.info("⏳ Early calibration phase - baseline still learning")
            else:
                logger.info("🎯 Late calibration phase - baseline should stabilize soon")

        # Start continuous data collection
        logger.info("🎬 Starting continuous sensor monitoring...")
        sensor.get_data(interval=READ_INTERVAL)

    except KeyboardInterrupt:
        logger.info("🛑 Pipeline stopped by user")
    except Exception as e:
        logger.error(f"❌ Pipeline failed: {e}")
        if args.debug:
            logger.exception("Full error traceback:")
        sys.exit(1)


if __name__ == "__main__":
    main()
