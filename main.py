import time
import json
import board
import busio
import displayio
from digitalio import DigitalInOut
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
from adafruit_esp32spi import adafruit_esp32spi
import adafruit_requests as requests
from adafruit_io.adafruit_io import IO_HTTP, AdafruitIO_RequestError
import adafruit_bmp3xx # Barometic Pressure, Altimeter
import adafruit_scd30 # CO2, Temperature, Humidity
import adafruit_pm25.i2c # Air Quality
import adafruit_ltr390 # UV
import adafruit_as7341 # Color
import adafruit_ssd1327 # Grayscale OLED Display
import conversions
import oled

try:
    from config import config
except ImportError:
    print('Could not locate configuration file.')
    raise

# Hardware definitions
resetPin = None
i2c = busio.I2C(board.SCL, board.SDA, frequency=100000) # frequency added for Air Quality sensor
bmp = adafruit_bmp3xx.BMP3XX_I2C(i2c)
scd = adafruit_scd30.SCD30(i2c) # board.I2C
pm25 = adafruit_pm25.i2c.PM25_I2C(i2c, resetPin)
ltr = adafruit_ltr390.LTR390(i2c)
asc = adafruit_as7341.AS7341(i2c)
displayBus = displayio.I2CDisplay(i2c, device_address=0x3D)
display = adafruit_ssd1327.SSD1327(displayBus, width=128, height=128)

# Prepare the display
splash = displayio.Group(max_size=10)
display.show(splash)

# If you are using a board with pre-defined ESP32 Pins:
esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)

# If you have an externally connected ESP32:
# esp32_cs = DigitalInOut(board.D9)
# esp32_ready = DigitalInOut(board.D10)
# esp32_reset = DigitalInOut(board.D5)

spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

print('Connecting to network...')
while not esp.is_connected:
    try:
        esp.connect_AP(config['ssid'], config['password'])
    except RuntimeError as ex:
        print('Could not connect to network, retrying: ', ex)
        continue
print('Connected to', str(esp.ssid, 'utf-8'), '\tRSSI:', esp.rssi)

socket.set_interface(esp)
requests.set_socket(socket, esp)

username = config['username']
key = config['key']
io = IO_HTTP(username, key, requests)

feedName = config['feed']
try:
    feed = io.get_feed(feedName)
except AdafruitIO_RequestError:
    feed = io.create_new_feed(feedName)

time.sleep(1)

while True:
    altitude = config['altitude']
    scd.altitude = altitude
    try:
        airQuality = pm25.read()
    except RuntimeError:
        print('Waiting for air quality data...')
        continue


    environmentalData = {
        'location' : {
            'name' : config['location'],
            'latitude' : config['latitude'],
            'longitude' : config['longitude'],
            'altitude' : {
                'defined' : altitude,
                'calculated' : bmp.altitude
            }
        },
        'pressure' : {
            'station' : bmp.pressure,
            'seaLevel': bmp.sea_level_pressure
        },
        'temperature' : {
            'celcius' : scd.temperature,
            'farenheight' : conversions.CtoF(scd.temperature)
        },
        'humidity' : scd.relative_humidity,
        'airQuality' : {
            'co2' : scd.CO2,
            'standard' : {
                'pm10' : airQuality['pm10 standard'],
                'pm25' : airQuality['pm25 standard'],
                'pm100' : airQuality['pm100 standard']
            },
            'environmental' : {
                'pm10' : airQuality['pm10 environmental'],
                'pm25' : airQuality['pm25 environmental'],
                'pm100' : airQuality['pm100 environmental']
            },
            'particles' : {
                '0-3microns' : airQuality['particles 03um'],
                '0-5microns' : airQuality['particles 05um'],
                '1-0microns' : airQuality['particles 10um'],
                '2-5microns' : airQuality['particles 25um'],
                '5-0microns' : airQuality['particles 50um'],
                '10-0microns' : airQuality['particles 100um'],
            }
        },
        'light' : {
            'uv' : ltr.uvs,
            'ambient' : ltr.light,
            'wavelengths' : {
                'violet' : asc.channel_415nm,
                'indigo' : asc.channel_480nm,
                'blue' : asc.channel_515nm,
                'green' : asc.channel_555nm,
                'yellow' : asc.channel_590nm,
                'orange' : asc.channel_630nm,
                'red' : asc.channel_680nm
            },
            'flicker' : asc.flicker_detected
        }
    }

    payload = json.dumps(environmentalData)

    print('Sending data to database...')
    io.send_data(feed['key'], payload)

    
    # Write to display
    oled.WriteToDisplay(display, scd.temperature, 5)

    time.sleep(0.5)
