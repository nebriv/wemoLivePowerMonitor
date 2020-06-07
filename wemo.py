import pywemo
import time
import os
import datetime
import threading
import pickle
import random
import mimetypes
from elasticsearch7 import Elasticsearch




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

    lastLoadTime = False

    fakeData = True

    es = False

    def __init__(self, esHost, esUser, esPass, esPort=9000, bgRun=True):
        self.es = Elasticsearch([esHost],
                                http_auth=(esUser, esPass),
                                ssl_show_warn=False,
                                verify_certs=False,
                                port=esPort)

        # if not self.es.ping():
        #     print(self.es.ping())
        #     raise ConnectionError("Error connecting to Elasticsearch host: %s" % esHost)

        print(self.es.info())

        self.load()
        self.bgRun = bgRun

        self.loadHistory()

        if self.bgRun:
            self.bgUpdateThread = threading.Thread(target=self.update)
            self.bgUpdateThread.start()


    def load(self):
        if not self.lastLoadTime:
            self.discovery()
            self.lastLoadTime = datetime.datetime.now()
        else:
            now = datetime.datetime.now()
            if (now - self.lastLoadTime).seconds > 3600:
                self.lastLoadTime = datetime.datetime.now()
                self.discovery()

    def discovery(self):
        print("Discovery Wemo devices on network")
        print("Discovery pass 1")
        devicesA = pywemo.discover_devices()
        time.sleep(2)
        print("Discovery pass 2")
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

    def saveHistory(self):
        pickle.dump(self.history, open('history.p', 'wb'))

    def loadHistory(self):
        if os.path.exists('history.p'):
            self.history = pickle.load(open('history.p', 'rb'))

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
        print(infoData['datetime'])
        res = self.es.index(index="wemo-%s-%s-%s" % (infoData['name'].replace(" ","").lower(),infoData['macaddress'].replace(":","").lower(), infoData['datetime'].strftime('%Y-%m-%d')), body=infoData)
        print(res)

    def collectDeviceInfo(self, historyLimit=60):
        now = datetime.datetime.utcnow()
        info = {"devices": []}

        for device in self.devices:
            state = device.get_state(force_update=True)
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

        return info

    def updateInsight(self):
        now = datetime.datetime.now()

        for device in self.devices:
            if not self.lastInsightUpdate:
                self.lastInsightUpdate = now
            elif (now - self.lastInsightUpdate).seconds > self.insightDataCacheTime:
                print("Updating insight data")
                device.update_insight_params()
                self.lastInsightUpdate = now

    def print_power_data(self):
        self.updateInsight()
        for device in self.devices:
            print(device.name)
            print(device.current_power)

    def print_total_power(self):

        print("Total power (kw): %s" % (self.total_power() / 1000000))

    def total_power(self, conversion=1000):
        deviceData = {}
        if len(self.devices) > 0:
            now = datetime.datetime.now()
            self.updateInsight()
            total = 0
            for device in self.devices:
                if device.name in self.history['devices']:
                    self.history['devices'][device.name]['data'].append(round(device.current_power / conversion, 2))
                    self.history['devices'][device.name]['dateValue'].append(now)
                else:
                    self.history['devices'][device.name] = {"dateValue": [], "data": []}
                    self.history['devices'][device.name]['data'].append(round(device.current_power / conversion, 2))
                    self.history['devices'][device.name]['dateValue'].append(now)
                deviceData[device.name] = {"dateValue": now, "data": round(device.current_power / conversion, 2)}

                total += device.current_power

            total = total / conversion
            self.addHistory(now, total)
        else:
            if self.fakeData:
                total = random.random()

        return {"datetime": now, "data": total, "deviceData": deviceData}

    def data_history(self):
        return self.history['total_power']

    def addHistory(self, timeData, data):
        self.history['total_power']['datetime'].append(timeData)
        self.history['total_power']['data'].append(data)

        if len(self.history['total_power']['datetime']) > self.historyMax:
            self.history['total_power']['datetime'].pop(0)
            self.history['total_power']['data'].pop(0)

    def update(self):
        while self.bgRun:
            #self.total_power()
            self.collectDeviceInfo()
            self.load()
            self.saveHistory()
            time.sleep(15)