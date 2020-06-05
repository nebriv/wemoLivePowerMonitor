import pywemo
import time
import os
import datetime
import threading
import pickle

class Wemo:
    devices = []
    cache_file = "wemo.cache"


    lastInsightUpdate = False
    insightDataCacheTime = 15
    bgRun = True
    history = {"total_power": {"datetime": [], "data": []}}
    historyMax = 360

    lastLoadTime = False

    def __init__(self, bgRun=True):
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
            print("Mismatch in number of detected devices. Trying again in 15 seconds.")
            time.sleep(15)
            self.discovery()

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

    def total_power(self, conversion=1000000):
        now = datetime.datetime.now()
        self.updateInsight()
        total = 0
        for device in self.devices:
            total += device.current_power

        total = total / conversion
        self.addHistory(now, total)
        return {"datetime": now, "data": total}

    def data_history(self):
        return self.history['total_power']

    def addHistory(self, timeData, data):
        self.history['total_power']['datetime'].append(timeData)
        self.history['total_power']['data'].append(data)

    def update(self):
        while self.bgRun:
            self.total_power()
            self.load()
            self.saveHistory()
            time.sleep(30)