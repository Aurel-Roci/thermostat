sudo useradd --system --no-create-home --shell /usr/sbin/nologin thermostat

#for SPI devices (if needed later)
#to communicate with BME680 sensor; for GPIO pin access

sudo usermod -a -G i2c,spi,gpio thermostat

sudo chown -R aurel:thermostat /home/aurel/thermostat
sudo chmod -R 750 /home/aurel/thermostat

sudo mkdir -p /etc/thermostat
sudo cp /home/aurel/thermostat/.env /etc/thermostat/thermostat.conf
sudo chown thermostat:thermostat /etc/thermostat/thermostat.conf
sudo chmod 640 /etc/thermostat/thermostat.conf

sudo cp bme680-sensor /etc/systemd/system/
