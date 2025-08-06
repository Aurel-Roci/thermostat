import ctypes
import os
import time
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class BSECWrapper:
    """
    Python wrapper for BSEC library - Step 1: Basic structure
    """

    def __init__(self, library_path: str = None):
        """
        Initialize BSEC wrapper

        Args:
            library_path: Path to libalgobsec.a or .so file
        """
        self.library_path = library_path or self._find_library()
        self.bsec_lib = None
        self.initialized = False

        # BSEC state
        self.state_file = "/tmp/bsec_state.dat"

        logger.info(f"Initializing BSEC wrapper with library: {self.library_path}")

    def _find_library(self) -> Optional[str]:
        """Find BSEC library file"""
        possible_paths = [
            "./bsec/rpi/bin/libbsec_wrapper.so",  # Compiled wrapper
            "./bsec/rpi/bin/libalgobsec.a",
            "/usr/local/lib/libalgobsec.so",
            "./libalgobsec.so",
            "/opt/bsec/libalgobsec.so"
        ]

        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Found BSEC library at: {path}")
                return path

        logger.error("BSEC library not found!")
        return None

    def _load_library(self) -> bool:
        """Load the BSEC shared library"""
        if not self.library_path or not os.path.exists(self.library_path):
            logger.error(f"BSEC library not found at: {self.library_path}")
            return False

        try:
            if self.library_path.endswith('.a'):
                logger.error("Static library (.a) found. Need shared library (.so)")
                logger.info("Run: gcc -shared -fPIC -I./inc -o libbsec_wrapper.so bsec_py_wrapper.c libalgobsec.a -lm")
                return False

            self.bsec_lib = ctypes.CDLL(self.library_path)

            self._setup_function_signatures()

            logger.info("✅ BSEC library loaded successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to load BSEC library: {e}")
            return False

    def _setup_function_signatures(self):
        """Set up ctypes function signatures"""
        try:
            # py_bsec_init() -> int
            self.bsec_lib.py_bsec_init.restype = ctypes.c_int
            self.bsec_lib.py_bsec_init.argtypes = []

            # py_bsec_get_version(int*, int*, int*, int*)
            self.bsec_lib.py_bsec_get_version.restype = None
            self.bsec_lib.py_bsec_get_version.argtypes = [
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int)
            ]

            # py_bsec_do_steps(float, float, float, float, uint64_t, float*, int*, float*, float*) -> int
            self.bsec_lib.py_bsec_do_steps.restype = ctypes.c_int
            self.bsec_lib.py_bsec_do_steps.argtypes = [
                ctypes.c_float,  # temperature
                ctypes.c_float,  # humidity
                ctypes.c_float,  # pressure
                ctypes.c_float,  # gas_resistance
                ctypes.c_uint64, # timestamp_ns
                ctypes.POINTER(ctypes.c_float),  # iaq
                ctypes.POINTER(ctypes.c_int),    # iaq_accuracy
                ctypes.POINTER(ctypes.c_float),  # co2_equivalent
                ctypes.POINTER(ctypes.c_float)   # breath_voc_equivalent
            ]

            logger.debug("Function signatures set up successfully")

        except Exception as e:
            logger.error(f"Failed to set up function signatures: {e}")
            raise

    def initialize(self) -> bool:
        """Initialize BSEC library"""
        if not self._load_library():
            return False

        try:
            result = self.bsec_lib.py_bsec_init()
            if result == 0:
                logger.info("✅ BSEC initialized successfully")
                self.initialized = True
                return True
            else:
                logger.error(f"❌ BSEC initialization failed with code: {result}")
                return False

        except Exception as e:
            logger.error(f"❌ BSEC initialization failed: {e}")
            return False

    def process_reading(self, temperature: float, humidity: float,
                       pressure: float, gas_resistance: float) -> Optional[Dict]:
        """
        Process sensor reading through BSEC

        Args:
            temperature: Temperature in °C
            humidity: Relative humidity in %
            pressure: Pressure in hPa
            gas_resistance: Gas resistance in Ω

        Returns:
            Dict with BSEC outputs or None if failed
        """
        if not self.initialized:
            logger.error("BSEC not initialized")
            return None

        try:
            timestamp_ns = int(time.time() * 1_000_000_000)

            iaq = ctypes.c_float()
            iaq_accuracy = ctypes.c_int()
            co2_equivalent = ctypes.c_float()
            breath_voc_equivalent = ctypes.c_float()

            result = self.bsec_lib.py_bsec_do_steps(
                ctypes.c_float(temperature),
                ctypes.c_float(humidity),
                ctypes.c_float(pressure),
                ctypes.c_float(gas_resistance),
                ctypes.c_uint64(timestamp_ns),
                ctypes.byref(iaq),
                ctypes.byref(iaq_accuracy),
                ctypes.byref(co2_equivalent),
                ctypes.byref(breath_voc_equivalent)
            )

            if result == 0:
                bsec_result = {
                    'timestamp_ns': timestamp_ns,
                    'iaq': iaq.value,
                    'iaq_accuracy': iaq_accuracy.value,
                    'static_iaq': iaq.value,  # Same as IAQ for now
                    'co2_equivalent': co2_equivalent.value,
                    'breath_voc_equivalent': breath_voc_equivalent.value,
                    'comp_gas_value': gas_resistance,
                    'gas_percentage': 50.0,  # Will calculate properly later
                    'stabilization_status': 0,
                    'run_in_status': 0
                }

                logger.debug(f"BSEC processing: T={temperature}°C, RH={humidity}%, "
                            f"P={pressure}hPa, Gas={gas_resistance}Ω -> IAQ={iaq.value:.1f}")

                return bsec_result
            else:
                logger.error(f"BSEC processing failed with code: {result}")
                return None

        except Exception as e:
            logger.error(f"❌ BSEC processing failed: {e}")
            return None

    def get_version(self) -> Dict:
        """Get BSEC version information"""
        if not self.initialized:
            return {
                "major": 2,
                "minor": 6,
                "major_bugfix": 1,
                "minor_bugfix": 0,
                "wrapper_version": "0.1.0",
                "status": "not_initialized"
            }

        try:
            major = ctypes.c_int()
            minor = ctypes.c_int()
            major_bugfix = ctypes.c_int()
            minor_bugfix = ctypes.c_int()

            self.bsec_lib.py_bsec_get_version(
                ctypes.byref(major),
                ctypes.byref(minor),
                ctypes.byref(major_bugfix),
                ctypes.byref(minor_bugfix)
            )

            return {
                "major": major.value,
                "minor": minor.value,
                "major_bugfix": major_bugfix.value,
                "minor_bugfix": minor_bugfix.value,
                "wrapper_version": "0.1.0",
                "status": "initialized"
            }

        except Exception as e:
            logger.error(f"Failed to get BSEC version: {e}")
            return {
                "error": str(e),
                "wrapper_version": "0.1.0"
            }

    def is_available(self) -> bool:
        return self.initialized

    def save_state(self) -> bool:
        """Save BSEC state to file"""
        # Placeholder - will implement once BSEC functions are working
        logger.info("💾 BSEC state save - placeholder")
        return True

    def load_state(self) -> bool:
        """Load BSEC state from file"""
        # Placeholder - will implement once BSEC functions are working
        if os.path.exists(self.state_file):
            logger.info("📂 BSEC state load - placeholder")
            return True
        return False
