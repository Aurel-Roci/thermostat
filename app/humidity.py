import adafruit_dht as DHT
import board
import time


DHT_PIN = board.D4
DHT_SENSOR = DHT.DHT22(DHT_PIN, False)


class Sensor(object):

    def __init__(self, db):
        self.db = db

    def get_data(self):
        while True:
            try:
                humidity = DHT_SENSOR.humidity
                temperature = DHT_SENSOR.temperature
                print("Temp={0:0.1f}*C   Humidity={1:0.1f}%".format(temperature, humidity))
                self.db.write([{
                    "measurement": "temperature",
                    "tags": {"sensor": "DHT22", "data": "celsius"},
                    "fields": {
                        "value": temperature,
                    }
                },
                    {
                        "measurement": "humidity",
                        "tags": {"sensor": "DHT22", "data": "percentage"},
                        "fields": {
                            "value": humidity,
                     }
                    }
                ])
                time.sleep(2.0)
            except RuntimeError as error:
                # Errors happen fairly often, DHT's are hard to read, just keep going
                print(error.args[0])
                time.sleep(2.0)
                continue
