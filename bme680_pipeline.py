import os
import sys
import logging
import argparse
from dotenv import load_dotenv
from app.database import VictoriaMetricsClient
from app.enhanced_bme680 import EnhancedBME680Sensor

# Load environment variables
load_dotenv()

# Configuration
VM_HOST = os.getenv('VM_HOST', 'localhost')
VM_PORT = os.getenv('VM_PORT', '8428')
DEVICE_ID = os.getenv('DEVICE_ID', 'pi4_bme680_enhanced')
READ_INTERVAL = int(os.getenv('READ_INTERVAL', '30'))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_argument_parser():
    """Setup command line argument parser"""
    parser = argparse.ArgumentParser(description='Enhanced BME680 → VictoriaMetrics Pipeline with BSEC')

    # BSEC-specific options
    parser.add_argument('--disable-bsec', action='store_true',
                       help='Disable BSEC and use fallback air quality processing')
    parser.add_argument('--bsec-status', action='store_true',
                       help='Show BSEC status and calibration info')

    # Legacy calibration options (for fallback mode)
    parser.add_argument('--reset-calibration', action='store_true',
                       help='Reset fallback air quality calibration')
    parser.add_argument('--force-complete-calibration', action='store_true',
                       help='Mark fallback calibration as complete')
    parser.add_argument('--show-calibration-status', action='store_true',
                       help='Show current calibration status')

    # General options
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    parser.add_argument('--test-reading', action='store_true',
                       help='Take a single test reading and exit')

    return parser


def main():
    """Main pipeline function with BSEC support"""

    # Parse command line arguments
    parser = setup_argument_parser()
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("🐛 Debug logging enabled")

    logger.info("🚀 Starting Enhanced BME680 → VictoriaMetrics Pipeline")
    logger.info(f"📊 Target: {VM_HOST}:{VM_PORT}")
    logger.info(f"🔧 Device ID: {DEVICE_ID}")
    logger.info(f"⏱️ Read Interval: {READ_INTERVAL}s")

    # Determine BSEC usage
    use_bsec = not args.disable_bsec
    logger.info(f"🧠 BSEC Processing: {'Enabled' if use_bsec else 'Disabled (using fallback)'}")

    try:
        db = VictoriaMetricsClient(host=VM_HOST, port=VM_PORT)

        if not db.health_check():
            logger.warning("⚠️ VictoriaMetrics health check failed, but continuing...")

        sensor = EnhancedBME680Sensor(db=db, device_id=DEVICE_ID, use_bsec=use_bsec)

        # Handle status and test commands
        if args.bsec_status:
            logger.info("📋 Enhanced BME680 Status:")
            status = sensor.get_status()
            calibration = sensor.get_calibration_status()

            logger.info(f"  Sensor: {'✅ OK' if status['sensor_initialized'] else '❌ Failed'}")
            logger.info(f"  BSEC: {'✅ Available' if status['bsec_available'] else '❌ Not Available'}")
            logger.info(f"  Processing Mode: {status['processing_mode']}")

            if status['bsec_available']:
                bsec_version = status['bsec_version']
                logger.info(f"  BSEC Version: {bsec_version['major']}.{bsec_version['minor']}.{bsec_version['major_bugfix']}.{bsec_version['minor_bugfix']}")
                logger.info(f"  Calibration: {calibration['accuracy_status']} (Level {calibration['accuracy_level']})")

                if calibration['calibration_complete']:
                    logger.info(f"  IAQ: {calibration['iaq_value']:.1f} ({calibration['iaq_status']})")
                else:
                    logger.info("  IAQ: Calibrating... (place sensor in clean air)")
            else:
                logger.info(f"  Fallback Calibration: {'✅ Complete' if calibration['calibration_complete'] else '🔧 In Progress'}")
                if calibration.get('baseline_value'):
                    logger.info(f"  Baseline: {calibration['baseline_value']:.0f}Ω")

            return

        if args.test_reading:
            logger.info("🧪 Taking test reading...")
            reading = sensor.single_reading()
            if reading:
                processing_mode = reading.get('_processing_mode', 'unknown')
                logger.info(f"✅ Test reading successful ({processing_mode} mode):")
                logger.info(f"  Temperature: {reading['temperature']}°C")
                logger.info(f"  Humidity: {reading['humidity']}%")
                logger.info(f"  Pressure: {reading['pressure']}hPa")
                logger.info(f"  Gas Resistance: {reading['gas_resistance']:.0f}Ω")

                if processing_mode == 'bsec':
                    logger.info(f"  IAQ: {reading.get('iaq', 'N/A'):.1f} ({reading.get('_iaq_status', 'Unknown')})")
                    logger.info(f"  CO2 Equivalent: {reading.get('co2_equivalent', 'N/A'):.0f}ppm")
                    logger.info(f"  VOC Equivalent: {reading.get('breath_voc_equivalent', 'N/A'):.2f}ppm")
                    logger.info(f"  Accuracy: {reading.get('_accuracy_status', 'Unknown')}")
                elif processing_mode == 'fallback':
                    logger.info(f"  Air Quality: {reading.get('air_quality_score', 'N/A')}/100 ({reading.get('_air_quality_status', 'Unknown')})")
                    logger.info(f"  Baseline: {reading.get('baseline_value', 'N/A'):.0f}Ω")
            else:
                logger.error("❌ Test reading failed")
            return

        # Handle legacy calibration commands (for fallback mode)
        if args.reset_calibration:
            if sensor.air_quality_fallback:
                logger.info("🔄 Resetting fallback air quality calibration...")
                sensor.air_quality_fallback.reset_calibration()
                logger.info("✅ Fallback calibration reset complete")
            else:
                logger.warning("⚠️ No fallback calibration to reset")
            return

        if args.force_complete_calibration:
            if sensor.air_quality_fallback:
                logger.info("⚡ Forcing fallback calibration completion...")
                sensor.air_quality_fallback.force_calibration_complete()
                logger.info("✅ Fallback calibration marked as complete")
            else:
                logger.warning("⚠️ No fallback calibration to complete")
            return

        if args.show_calibration_status:
            logger.info("📋 Current Calibration Status:")
            calibration = sensor.get_calibration_status()

            if calibration['mode'] == 'bsec':
                logger.info("  Mode: BSEC")
                logger.info(f"  Accuracy: {calibration['accuracy_status']} (Level {calibration['accuracy_level']})")
                logger.info(f"  IAQ: {calibration.get('iaq_value', 'N/A'):.1f} ({calibration.get('iaq_status', 'Unknown')})")
                logger.info(f"  Calibrated: {'✅ Yes' if calibration['calibration_complete'] else '🔧 In Progress'}")
            elif calibration['mode'] == 'fallback':
                logger.info("  Mode: Fallback")
                logger.info(f"  Calibrated: {'✅ Yes' if calibration['calibration_complete'] else '🔧 In Progress'}")
                logger.info(f"  Baseline: {calibration.get('baseline_value', 'N/A'):.0f}Ω")
                logger.info(f"  Air Quality: {calibration.get('air_quality_score', 'N/A')}/100")
            else:
                logger.info("  Mode: Raw only (no air quality processing)")
            return

        # Show startup status
        status = sensor.get_status()
        calibration = sensor.get_calibration_status()

        if status['bsec_available']:
            logger.info("🧠 Using BSEC for air quality processing (ULP mode - 5min intervals)")
            if calibration['calibration_complete']:
                logger.info(f"✅ BSEC calibrated: {calibration['accuracy_status']}")
            else:
                logger.info("🔧 BSEC calibrating: Place sensor in clean air for best results")
                logger.info("💡 BSEC calibration typically takes 5-30 minutes in clean air")
        elif sensor.air_quality_fallback:
            logger.info("📊 Using fallback air quality processing")
            if calibration['calibration_complete']:
                logger.info(f"✅ Using established baseline: {calibration.get('baseline_value', 0):.0f}Ω")
            else:
                logger.info("🔧 Fallback calibration in progress")
        else:
            logger.info("📊 Raw sensor readings only (no air quality processing)")

        logger.info("🎬 Starting continuous sensor monitoring...")
        sensor.get_data(interval=READ_INTERVAL)

    except KeyboardInterrupt:
        logger.info("🛑 Enhanced pipeline stopped by user")
    except Exception as e:
        logger.error(f"❌ Pipeline failed: {e}")
        if args.debug:
            logger.exception("Full error traceback:")
        sys.exit(1)


if __name__ == "__main__":
    main()
