import time
from datetime import datetime

import requests


def send_to_victoria_metrics(temperature, humidity, pressure, gas):
    vm_url = f"http://{VM_HOST}:{VM_PORT}/victoria-metrics/api/v1/import/prometheus"

    timestamp = int(datetime.now().timestamp() * 1000)  # milliseconds

    metrics = f"""
temperature{{device="pi4_bme680",sensor="bme680"}} {temperature} {timestamp}
humidity{{device="pi4_bme680",sensor="bme680"}} {humidity} {timestamp}
pressure{{device="pi4_bme680",sensor="bme680"}} {pressure} {timestamp}
gas_resistance{{device="pi4_bme680",sensor="bme680"}} {gas} {timestamp}
"""

    try:
        response = requests.post(vm_url, data=metrics.strip())
        if response.status_code == 204:
            print("✅ Data sent to VictoriaMetrics")
        else:
            print(f"❌ Error: {response.status_code}")
    except Exception as e:
        print(f"❌ Connection error: {e}")
