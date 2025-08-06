#include "inc/bsec_datatypes.h"
#include "inc/bsec_interface.h"
#include "config/bsec_iaq.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static bsec_sensor_configuration_t requested_virtual_sensors[8];
static uint8_t n_requested_virtual_sensors = 1;

int py_bsec_init() {
  bsec_library_return_t bsec_status = bsec_init();

  if (bsec_status != BSEC_OK) {
    return (int)bsec_status;
  }

  printf("BSEC basic init successful\n");

  bsec_status = bsec_set_configuration(bsec_config_iaq, sizeof(bsec_config_iaq), NULL, 0);
  if (bsec_status != BSEC_OK) {
      printf("⚠️ Config from .h file failed: %d (trying without config)\n", (int)bsec_status);
  } else {
      printf("✅ LP mode config from .h file loaded successfully\n");
  }

  // Try LP mode first (3 second intervals) - with ALL key sensors
  requested_virtual_sensors[0].sensor_id = BSEC_OUTPUT_IAQ;
  requested_virtual_sensors[0].sample_rate = BSEC_SAMPLE_RATE_LP;

  requested_virtual_sensors[1].sensor_id = BSEC_OUTPUT_STATIC_IAQ;
  requested_virtual_sensors[1].sample_rate = BSEC_SAMPLE_RATE_LP;

  requested_virtual_sensors[2].sensor_id = BSEC_OUTPUT_CO2_EQUIVALENT;
  requested_virtual_sensors[2].sample_rate = BSEC_SAMPLE_RATE_LP;

  requested_virtual_sensors[3].sensor_id = BSEC_OUTPUT_BREATH_VOC_EQUIVALENT;
  requested_virtual_sensors[3].sample_rate = BSEC_SAMPLE_RATE_LP;

  requested_virtual_sensors[4].sensor_id = BSEC_OUTPUT_COMPENSATED_GAS;
  requested_virtual_sensors[4].sample_rate = BSEC_SAMPLE_RATE_LP;

  requested_virtual_sensors[5].sensor_id = BSEC_OUTPUT_GAS_PERCENTAGE;
  requested_virtual_sensors[5].sample_rate = BSEC_SAMPLE_RATE_LP;

  requested_virtual_sensors[6].sensor_id = BSEC_OUTPUT_STABILIZATION_STATUS;
  requested_virtual_sensors[6].sample_rate = BSEC_SAMPLE_RATE_LP;

  requested_virtual_sensors[7].sensor_id = BSEC_OUTPUT_RUN_IN_STATUS;
  requested_virtual_sensors[7].sample_rate = BSEC_SAMPLE_RATE_LP;

  n_requested_virtual_sensors = 8;

  bsec_sensor_configuration_t
      required_sensor_settings[BSEC_MAX_PHYSICAL_SENSOR];
  uint8_t n_required_sensor_settings = BSEC_MAX_PHYSICAL_SENSOR;

  bsec_status = bsec_update_subscription(
      requested_virtual_sensors, n_requested_virtual_sensors,
      required_sensor_settings, &n_required_sensor_settings);

  printf("LP mode (3s intervals) result: %d\n", (int)bsec_status);

  if (bsec_status == BSEC_OK) {
    printf("Success with LP mode - 3 second intervals!\n");
    return 0;
  }

  // If LP fails, try SCAN mode (18s intervals)
  printf("LP failed, trying SCAN mode\n");
  requested_virtual_sensors[0].sample_rate =
      BSEC_SAMPLE_RATE_SCAN; // ~18 seconds
  requested_virtual_sensors[1].sample_rate =
      BSEC_SAMPLE_RATE_SCAN; // ~18 seconds
  requested_virtual_sensors[2].sample_rate =
      BSEC_SAMPLE_RATE_SCAN; // ~18 seconds
  requested_virtual_sensors[3].sample_rate =
      BSEC_SAMPLE_RATE_SCAN; // ~18 seconds
  requested_virtual_sensors[4].sample_rate =
      BSEC_SAMPLE_RATE_SCAN; // ~18 seconds
  requested_virtual_sensors[5].sample_rate =
      BSEC_SAMPLE_RATE_SCAN; // ~18 seconds
  requested_virtual_sensors[6].sample_rate =
      BSEC_SAMPLE_RATE_SCAN; // ~18 seconds
  requested_virtual_sensors[7].sample_rate =
      BSEC_SAMPLE_RATE_SCAN; // ~18 seconds

  bsec_status = bsec_update_subscription(
      requested_virtual_sensors, n_requested_virtual_sensors,
      required_sensor_settings, &n_required_sensor_settings);

  printf("SCAN mode (18s intervals) result: %d\n", (int)bsec_status);

  if (bsec_status == BSEC_OK) {
    printf("Success with SCAN mode - 18 second intervals!\n");
    return 0;
  }

  // Fall back to ULP if needed
  printf("SCAN failed, falling back to ULP\n");
  requested_virtual_sensors[0].sample_rate = BSEC_SAMPLE_RATE_ULP; // 5 minutes
  requested_virtual_sensors[1].sample_rate = BSEC_SAMPLE_RATE_ULP; // 5 minutes
  requested_virtual_sensors[2].sample_rate = BSEC_SAMPLE_RATE_ULP; // 5 minutes
  requested_virtual_sensors[3].sample_rate = BSEC_SAMPLE_RATE_ULP; // 5 minutes
  requested_virtual_sensors[4].sample_rate = BSEC_SAMPLE_RATE_ULP; // 5 minutes
  requested_virtual_sensors[5].sample_rate = BSEC_SAMPLE_RATE_ULP; // 5 minutes
  requested_virtual_sensors[6].sample_rate = BSEC_SAMPLE_RATE_ULP; // 5 minutes
  requested_virtual_sensors[7].sample_rate = BSEC_SAMPLE_RATE_ULP; // 5 minutes
  bsec_status = bsec_update_subscription(
      requested_virtual_sensors, n_requested_virtual_sensors,
      required_sensor_settings, &n_required_sensor_settings);

  return (int)bsec_status;
}

void py_bsec_get_version(int *major, int *minor, int *major_bugfix,
                         int *minor_bugfix) {
  bsec_version_t version;
  bsec_get_version(&version);
  *major = version.major;
  *minor = version.minor;
  *major_bugfix = version.major_bugfix;
  *minor_bugfix = version.minor_bugfix;
}

int py_bsec_do_steps(float temperature, float humidity, float pressure,
                     float gas_resistance, uint64_t timestamp_ns, float *iaq,
                     int *iaq_accuracy, float *co2_equivalent,
                     float *breath_voc_equivalent) {

  bsec_input_t inputs[4];
  uint8_t n_inputs = 4;

  inputs[0].sensor_id = BSEC_INPUT_TEMPERATURE;
  inputs[0].signal = temperature;
  inputs[0].time_stamp = timestamp_ns;

  inputs[1].sensor_id = BSEC_INPUT_HUMIDITY;
  inputs[1].signal = humidity;
  inputs[1].time_stamp = timestamp_ns;

  inputs[2].sensor_id = BSEC_INPUT_PRESSURE;
  inputs[2].signal = pressure * 100.0f; // Convert hPa to Pa
  inputs[2].time_stamp = timestamp_ns;

  inputs[3].sensor_id = BSEC_INPUT_GASRESISTOR;
  inputs[3].signal = gas_resistance;
  inputs[3].time_stamp = timestamp_ns;

  bsec_output_t outputs[8];  // Subscribed sensors
  uint8_t n_outputs = 8;

  bsec_library_return_t bsec_status =
      bsec_do_steps(inputs, n_inputs, outputs, &n_outputs);

  printf("BSEC result: status=%d, actual_outputs=%d\n", (int)bsec_status, n_outputs);

  if (bsec_status != BSEC_OK) {
    return (int)bsec_status;
  }

  // Default values
  *iaq = 25.0f;
  *iaq_accuracy = 0;
  *co2_equivalent = 400.0f;
  *breath_voc_equivalent = 0.5f;

  for (uint8_t i = 0; i < n_outputs; i++) {
    switch (outputs[i].sensor_id) {
    case BSEC_OUTPUT_IAQ:
      *iaq = outputs[i].signal;
      *iaq_accuracy = (int)outputs[i].accuracy;
      break;
    case BSEC_OUTPUT_CO2_EQUIVALENT:
      *co2_equivalent = outputs[i].signal;
      break;
    case BSEC_OUTPUT_BREATH_VOC_EQUIVALENT:
      *breath_voc_equivalent = outputs[i].signal;
      break;
    }
  }

  printf("Final values: IAQ=%.1f (acc=%d), CO2=%.0f, VOC=%.2f\n",
         *iaq, *iaq_accuracy, *co2_equivalent, *breath_voc_equivalent);

  return 0;
}
