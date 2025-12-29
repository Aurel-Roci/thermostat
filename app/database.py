import logging
from datetime import datetime
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)


class VictoriaMetricsClient:
    """Client for sending metrics to VictoriaMetrics"""

    def __init__(self, host: str = "localhost", port: str = "8428"):
        self.host = host
        self.port = port
        self.url = f"http://{host}:{port}/victoria-metrics/api/v1/import/prometheus"
        logger.info(f"VictoriaMetrics client initialized: {self.url}")

    def write_metrics(
        self, metrics_data: Dict[str, float], tags: Dict[str, str]
    ) -> bool:
        """
        Write metrics to VictoriaMetrics

        Args:
            metrics_data: Dictionary of metric_name -> value
            tags: Dictionary of tag_name -> tag_value

        Returns:
            bool: True if successful, False otherwise
        """
        if not metrics_data:
            logger.warning("No metrics data provided")
            return False

        timestamp = int(datetime.now().timestamp() * 1000)  # milliseconds

        # Build tag string
        tag_string = ",".join([f'{k}="{v}"' for k, v in tags.items()])

        # Create Prometheus format metrics
        metrics_lines = []
        for metric_name, value in metrics_data.items():
            if value is not None:  # Skip None values
                metric_line = f"{metric_name}{{{tag_string}}} {value} {timestamp}"
                metrics_lines.append(metric_line)

        if not metrics_lines:
            logger.warning("No valid metrics to send")
            return False

        metrics_payload = "\n".join(metrics_lines)

        try:
            response = requests.post(
                self.url,
                data=metrics_payload,
                headers={"Content-Type": "text/plain"},
                timeout=10,
            )

            if response.status_code == 204:
                logger.info(
                    f"✅ Metrics sent successfully: {len(metrics_lines)} metrics"
                )
                logger.debug(f"Metrics: {list(metrics_data.keys())}")
                return True
            else:
                logger.error(
                    f"❌ VictoriaMetrics error: {response.status_code} - {response.text}"
                )
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Connection error: {e}")
            return False

    def write_sensor_data(self, device_id: str, sensor_type: str, **readings) -> bool:
        """
        Convenience method for writing sensor data

        Args:
            device_id: Unique device identifier
            sensor_type: Type of sensor (dht22, bme680, etc.)
            **readings: Sensor readings as keyword arguments

        Returns:
            bool: True if successful, False otherwise
        """
        tags = {"device": device_id, "sensor": sensor_type}

        return self.write_metrics(readings, tags)

    def health_check(self) -> bool:
        """Check if VictoriaMetrics is reachable"""
        try:
            health_url = f"http://{self.host}:{self.port}/health"
            response = requests.get(health_url, timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
