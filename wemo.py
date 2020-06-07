import pywemo
import time
import os
import datetime
import threading
import pickle
import random
import mimetypes
from elasticsearch7 import Elasticsearch

from pywemo.ouimeaux_device.api.service import ActionException


mimetypes.add_type('text/css', '.css')
mimetypes.add_type('text/javascript', '.js')
class Wemo:
    devices = []
    cache_file = "wemo.cache"


    lastInsightUpdate = False
    insightDataCacheTime = 15
    bgRun = True
    history = {"total_power": {"datetime": [], "data": []}, "devices": {}}
    historyMax = 360000

    firstRun = True
    lastDiscoveryTime = datetime.datetime.now()
    rediscoverTries = 0

    fakeData = True

    es = False
    config = False
    alwaysOnDevices = []

    def __init__(self, config, bgRun=True):
        self.config = config
        if "Elasticsearch" in config:
            esHost = config['Elasticsearch']['host']
            esUser = config['Elasticsearch']['username']
            esPass = config['Elasticsearch']['password']
            esPort = config['Elasticsearch']['port']
            self.es = Elasticsearch([esHost],
                                    http_auth=(esUser, esPass),
                                    ssl_show_warn=False,
                                    verify_certs=False,
                                    port=esPort)

        if "Wemo" in config:
            if "AlwaysOn" in config['Wemo']:
                print("Loading always on devices")
                self.alwaysOnDevices = config['Wemo']['AlwaysOn'].split(",")

        if self.es:
            if not self.es.ping():
                print(self.es.ping())
                raise ConnectionError("Error connecting to Elasticsearch host: %s" % esHost)

        self.discovery()
        self.bgRun = bgRun

        if self.bgRun:
            self.bgUpdateThread = threading.Thread(target=self.update)
            self.bgUpdateThread.start()

    def discovery(self):
        now = datetime.datetime.now()
        if self.firstRun:
            self.lastDiscoveryTime = now - datetime.timedelta(seconds=180)
        if (now - self.lastDiscoveryTime).seconds > 90:
            self.lastDiscoveryTime = now
            print("Discovering Wemo devices on network")
            devicesA = pywemo.discover_devices()
            time.sleep(2)
            devicesB = pywemo.discover_devices()
            if len(devicesA) == len(devicesB):
                self.devices = devicesB
                for device in self.devices:
                    print(device.host)
                self.save_cache()
            else:
                print("Mismatch in number of detected devices. Trying again in 5 seconds.")
                time.sleep(5)
                self.discovery()
            if len(self.devices) == 0:
                print("OH GOD OH NO. NO WEMO DEVICES!")
                if self.fakeData:
                    print("but don't worry we'll just make some data up...")

    def load_cache(self):
        print("Loading cache: %s" % self.cache_file)
        with open(self.cache_file, 'r') as inFile:
            for line in inFile.readlines():
                address = line.strip()
                port = pywemo.ouimeaux_device.probe_wemo(address)
                url = 'http://%s:%i/setup.xml' % (address, port)
                device = pywemo.discovery.device_from_description(url, None)
                self.devices.append(device)

    def save_cache(self):
        print("Saving cache: %s" % self.cache_file)
        with open(self.cache_file, 'w') as outFile:
            for device in self.devices:
                outFile.write(device.host + "\n")

    def writeInfotoES(self, infoData):
        # print(infoData['datetime'])
        res = self.es.index(index="wemo-%s-%s-%s" % (infoData['name'].replace(" ","").lower(),infoData['macaddress'].replace(":","").lower(), infoData['datetime'].strftime('%Y-%m-%d')), body=infoData)
        if "result" in res:
            if res['result'] == "created":
                return True
        return False
        # print(res)

    def collectDeviceInfo(self, historyLimit=60):
        now = datetime.datetime.utcnow()
        info = {"devices": []}

        for device in self.devices:
            deviceCommunicating = True
            try:
                state = device.get_state(force_update=True)
            except ActionException as err:
                print(err)
                deviceCommunicating = False

            if deviceCommunicating:
                device.update_insight_params()
                if state == 8:
                    state = "Standby"
                elif state == 1:
                    state = "On"
                elif state == 0:
                    state = "off"

                data = {"name": device.name,
                        "datetime": now,
                        'macaddress': device.mac,
                        "status": state,
                        "ontoday": device.today_on_time,
                        "todaykwh": round(device.today_kwh, 2),
                        "currentPower": device.current_power,
                        "todayOnTime": device.today_on_time,
                        "onFor": device.on_for,
                        "todayStandbyTime": device.today_standby_time
                        }

                info['devices'].append(data)

                if self.es:
                    self.writeInfotoES(data)
            else:
                print("ERROR COMMUNICATING WITH %s. Re-running discovery." % device.name)
                if device.name in self.alwaysOnDevices:
                    print("OH GOD ITS A BAD ONE TO LOSE.")
                self.discovery()

        return info

    def print_power_data(self):
        self.updateInsight()
        for device in self.devices:
            print(device.name)
            print(device.current_power)

    def print_total_power(self):
        print("Total power (kw): %s" % (self.total_power() / 1000000))

    def alwaysOnDevice(self, device, flipped=0):
        if device.name in self.alwaysOnDevices:
            if device.get_state() == 0:
                print("%s is off! Turning it back on!" % device.name)
                device.on()
                time.sleep(1)
                if device.get_state(True) == 0:
                    if flipped <= 3:
                        flipped += 1
                        time.sleep(1)
                        self.alwaysOnDevice(device, flipped=flipped)
                    else:
                        print("%s is still off. Unable to turn it back on!" % device.name)

    def checkAlwaysOn(self):
        for device in self.devices:
            self.alwaysOnDevice(device)

        for device in self.alwaysOnDevices:
            if not any(x.name == device for x in self.devices):
                print("OH MY GOD %s IS MISSING!" % device)
                self.discovery()


    def update(self):
        while self.bgRun:
            #self.total_power()
            self.collectDeviceInfo()
            self.checkAlwaysOn()
            self.load()
            time.sleep(15)