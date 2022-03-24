from pyzbar import pyzbar
from subprocess import PIPE, run
from numpy import asarray
from PIL import Image
from time import sleep
import argparse
import RPi.GPIO as gpio
import logging as log


TMPFPATH = '/run/user/1000/tmpqr.png'
NODETECT_REPETITIONS = 2
ON_WAIT  = 0.2
OFF_WAIT = 3.0
 

def out(command):
    result = run(command, stdout=PIPE, stderr=PIPE, universal_newlines=True, shell=True)
    return result.stdout

def start(url):
    gpio.output(2,0)
    log.info("url detected: " + url)
    return True


def stop():
    gpio.output(2,1)
    log.info("nothing detected")
    return True


def loop():

    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--preview", help="Show image preview on hdmi output", action="store_true")
    parser.add_argument("-v", "--verbose", help="Set loglevel to INFO", action="store_true")
    args = parser.parse_args()

    log.basicConfig(format='%(levelname)s:%(message)s', level=log.INFO if args.verbose else log.WARNING)

    log.debug("this is a DEBUG message")
    log.info("this is an INFO message")
    log.error("this is an ERROR message")

    last_code = ''
    nothing_counter = 0
    wait = OFF_WAIT

    gpio.setmode(gpio.BCM)
    gpio.setup(2,gpio.OUT)
    gpio.output(2,1)

    command = "libcamera-still "

    if not args.preview:
        command += "-n --immediate "

    command += " -o " + TMPFPATH + " --height 400 --width 400"

    while True:

        output = out(command)
        img = Image.open(TMPFPATH)
        npd = asarray(img)

        barcodes = pyzbar.decode(npd)

        if len(barcodes) and barcodes[0].type == 'QRCODE':
            log.debug("qrcode found")
            barcode = barcodes[0].data.decode("utf-8")
            nothing_counter = NODETECT_REPETITIONS
            if barcode != last_code:
                if start(barcode):
                    wait = ON_WAIT
                    last_code = barcode
        else:
            log.debug("nothing found")
            if nothing_counter:
                nothing_counter -=1
            else:
                if last_code != '':
                    if stop():
                        last_code = ''
                        wait = OFF_WAIT

    #sleep(wait)

try:
    loop()
except KeyboardInterrupt:
    gpio.setup(2,gpio.IN)

