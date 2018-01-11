#!/usr/bin/python
#
# Change volume with the mouse scroll wheel
# Pause, play and previous, next track
#
# Preqrequisites
#   sudo apt-get install python-pip python-dev build-essential
#   sudo pip install --upgrade pip
#   sudo pip install --upgrade virtualenv
#   sudo pip install evdev
#   sudo apt-get install python-alsaaudio
#
#   sudo apt-get install python-rpi.gpio
#
#   node.js
#   roon api
#
# Verify with "ls /dev/input/*" which events apply for the mouse.
# Install the roon extension on your roon host (see link below).
#
# To configure
# - the roon server (is roon now)
# - the zone and output to control with the mouse
#
# Many thanks to:
#   https://www.raspberrypi.org/forums/viewtopic.php?t=42046
#   https://github.com/st0g1e/roon-extension-http-api
#
# To consider
# - Use mute from roon instead from IQAudio (is currently not defined in the roon extension)
# - Use minimum and maximum values from roon
#

import logging
import RPi.GPIO as GPIO
import requests
from evdev import InputDevice
import evdev
from select import select
import urllib2
import json
import signal
import sys

def signal_handler(signal, frame):
        logging.debug('You pressed Ctrl+C!')
        GPIO.cleanup()
        sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

#logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.info('Mouse volume control for roon.')

#dev = InputDevice('/dev/input/event1') # This can be any other event number. On$
dev = None
devices = [evdev.InputDevice(fn) for fn in evdev.list_devices()]
for device in devices:
        logging.debug("input: %s name:%s phys:%s", device.fn, device.name, device.phys)
        if device.name.find("Mouse") > 0:
                dev = InputDevice(device.fn)
                logging.debug("Mouse linked to event %s", device.fn)
if dev is None:
        logging.info('No mouse detected.')
        sys.exit(0)
logging.debug("%s", dev.capabilities(verbose=True))
# mute control pin
mutepin = 22
mute=False
GPIO.setmode(GPIO.BCM)
GPIO.setup(mutepin, GPIO.OUT)

#
# Configure the zone and the output that is linked to the mouse
#
zone_name = 'woonkamer'
output_name = 'woonkamer'

#
# Find the zone
#
link = 'http://roon:3001/roonAPI/listZones'
response = urllib2.urlopen(link)
data = json.load(response)
zones = data['zones']
logging.debug('Zones: ')
found = False
for zone in zones[:]:
        logging.debug("%s %s", zone['zone_id'],zone['display_name'])
        if zone['display_name'] == zone_name:
                zone_id = zone['zone_id']
                found = True

if found:
        logging.info('Found zone %s, id: %s', zone_name, zone_id)
else:
        logging.error("Zone %s not found!",zone_name)
        GPIO.cleanup()
        sys.exit(0)

link = 'http://roon:3001/roonAPI/getZone?zoneId='+zone_id
response = urllib2.urlopen(link)
data = json.load(response)

#
# Find the output for the zone in the returned data
#
logging.debug('Outputs for zone '+zone_name)
outputs = data['zone']['outputs']
for output in outputs[:]:
        if output['display_name'] == output_name:
                output_id = output['output_id']
                cur_vol = output['volume']['value']
                logging.info("%s %s volume: %s", output['output_id'], output['display_name'], cur_vol)
        else:
                logging.debug("%s %s", output['output_id'], output['display_name'])


def get_volume(zone_id):
        "get zone info (including current volume)"
        result = 0
        link = 'http://roon:3001/roonAPI/getZone?zoneId='+zone_id
        response = urllib2.urlopen(link)
        data = json.load(response)
        outputs = data['zone']['outputs']
        for output in outputs[:]:
                output_id = output['output_id']
                if output['display_name'] == output_name:
                        cur_vol = output['volume']['value']
                        logging.debug("%s %s, volume: %s", output['output_id'], output['display_name'], cur_vol)
                        result = cur_vol
                else:
                        logging.debug("%s %s", output_id, output['display_name'])
        return result

def play_previous(zone_id):
        "skip to previous track"
        logging.info("Previous track")
        link = "http://roon:3001/roonAPI/previous?zoneId="+zone_id
        f = requests.get(link)
        return

def play_next(zone_id):
        logging.info("Next track")
        link = "http://roon:3001/roonAPI/next?zoneId="+zone_id
        f = requests.get(link)
        return

def play_pause(zone_id):
        logging.info("Play/pause track")
        link = "http://roon:3001/roonAPI/play_pause?zoneId="+zone_id
        f = requests.get(link)
        return

def toggle_mute_hardware(mute):
        if (not mute):
                logging.info("Mute on")
                GPIO.output(mutepin,0)
                result=True
        else:
                logging.info("Mute off")
                GPIO.output(mutepin,1)
                result=False
        return result

def change_volume(output_id, new_vol):
        logging.info("Volume: %d", new_vol)
        link = 'http://roon:3001/roonAPI/change_volume?volume='+str(new_vol)+'&outputId=' + output_id
        response = urllib2.urlopen(link)

short_press = False
long_press = False

while True:
#       r,w,x = select([dev], [], [])
        r,w,x = select([dev], [], [], 0.4)
        if (r):
                for event in dev.read():
#                       print(event)
                        if event.code == 8 or event.code==6:  # scrollwheel
                                if (long_press):
                                        if event.value < 0:
                                                play_previous(zone_id)
                                        else:
                                                play_next(zone_id)
                                else:
                                        new_vol = get_volume(zone_id)
                                        new_vol = new_vol + event.value
                                        if new_vol < 0:
                                                new_vol=0
                                        elif new_vol > 100:
                                                new_vol=100
                                        change_volume(output_id, new_vol)
#                       elif event.code == 272:  # left
#                               if event.value==1:
#                                       play_previous(zone_id)
#                       elif event.code == 273:  # right
#                               if event.value==1:
#                                       play_next(zone_id)
#                       elif event.code == 277: # left up
#                               if (event.value==0):
#                                       mute = toggle_mute_hardware(mute)
#                       elif event.code ==278: # left down
#                               This event is not used.
                        elif event.code==274: # middle
                                if event.value==1:
                                        logging.debug("short press")
                                        short_press = True
                                else:
                                        if not long_press:
                                                play_pause(zone_id)
                                        short_press = False
                                        long_press = False
#                       elif (event.code <> 0 and event.code <> 1):
#                               print(event)
#                               logging.debug("Mouse event: %s", event.code)
        else:
                if (short_press and not long_press):
                        logging.debug("long press")
                        long_press = True

