import spidev
import time

spi = spidev.SpiDev()
spi.open(0, 0)

def read(channel):
    adc = spi.xfer2([1, (8 + channel) << 4, 0])
    data = ((adc[1] & 3) << 8) + adc[2]
    return data

while True:
    print("Light:", read(0))
    print("Moisture:", read(1))
    print("-----")
    time.sleep(2)
