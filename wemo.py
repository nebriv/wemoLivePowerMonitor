import pywemo
import time
import os
import datetime
import threading
import pickle
import random
import mimetypes
from elasticsearch7 import Elasticsearch
import clicksend_client
from clicksend_client.rest import ApiException
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

    smsAccountAPI = False
    smsAPI = False
    notificationNumber = False

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

        if "Notifications" in config:
            if "clicksendAPI_username" in config['Notifications']:
                configuration = clicksend_client.Configuration()
                configuration.username = config['Notifications']['clicksendAPI_username']
                configuration.password = config['Notifications']['clicksendAPI_password']
                self.notificationNumber = config['Notifications']['phonenumber']
                # create an instance of the API class
                self.smsAccountAPI = clicksend_client.AccountApi(clicksend_client.ApiClient(configuration))
                try:
                    # Get account information
                    api_response = self.smsAccountAPI.account_get()
                    if "http_code': 200" not in api_response:
                        print("Invalid clicksend API response")
                        print(api_response)
                        self.smsAccountAPI = False
                    else:
                        self.smsAPI = clicksend_client.SMSApi(clicksend_client.ApiClient(configuration))

                except ApiException as e:
                    print("Exception when calling AccountApi->account_get: %s\n" % e)
                except Exception as err:
                    print("Eception when calling clicksend API")
                    print(err)


        if "Wemo" in config:
            if "AlwaysOn" in config['Wemo']:
                print("Loading always on devices")
                self.alwaysOnDevices = config['Wemo']['AlwaysOn'].split(",")

        if self.es:
            print("Connecting to ES")
            try:
                if not self.es.ping():
                    print(self.es.ping())
                    raise ConnectionError("Error connecting to Elasticsearch host: %s" % esHost)
            except Exception as err:
                print("Error connecting to ES")
        self.discovery()
        self.bgRun = bgRun

        if self.bgRun:
            self.bgUpdateThread = threading.Thread(target=self.update)
            self.bgUpdateThread.start()

    def discovery(self, retry=0):
        now = datetime.datetime.now()
        if self.firstRun:
            self.lastDiscoveryTime = now - datetime.timedelta(seconds=10000000)
            self.firstRun = False
        if (now - self.lastDiscoveryTime).seconds > 300 or retry > 0:
            self.lastDiscoveryTime = now
            print("Discovering Wemo devices on network")
            devicesA = pywemo.discover_devices()
            time.sleep(2)
            devicesB = pywemo.discover_devices()
            if len(devicesA) == len(devicesB) and len(devicesA) > 0:
                self.devices = devicesB
                print("Found %s devices in discovery" % len(self.devices))
            else:
                if retry < 3:
                    retry += 1
                    print("Mismatch in number of detected devices, or no devices found. Trying again in 5 seconds.")
                    time.sleep(5)
                    self.discovery(retry)
                else:
                    print("%s retries and still unable to get devices... backing off a long time (We will never give up though. The fridge depends on us.)" % retry)
                    if retry > 10:
                        time.sleep(120)
                    else:
                        time.sleep(30)
                    retry += 1
                    self.discovery(retry)


    def sendSMSMessage(self, message, to, retry=0):
        if to.startswith("+1"):
            try:
                message = "Wemo Alert - %s " % message

                message = clicksend_client.SmsMessage(body=message, to=to)
                messages = clicksend_client.SmsMessageCollection(messages=[message])
                try:
                    # Send sms message(s)
                    api_response = self.smsAPI.sms_send_post(messages)
                    # print(api_response)
                except ApiException as e:
                    print("Exception when calling SMSApi->sms_send_post: %s\n" % e)
            except ConnectionResetError as err:
                print("Got an error sending SMS trying again...")
                time.sleep(1)
                if retry < 3:
                    retry += 1
                    self.sendSMSMessage(message, to, retry)
                else:
                    print("Still couldn't send that dang message. Giving up after 3 retries")

        else:
            print("Invalid phone number while trying to send message")

    def reDiscover(self, rediscoveryTime = 600):
        now = datetime.datetime.now()
        if (now - self.lastDiscoveryTime).seconds > rediscoveryTime:
            self.discovery()

    def writeInfotoES(self, infoData):
        # print(infoData['datetime'])
        try:
            res = self.es.index(index="wemo-%s-%s-%s" % (infoData['name'].replace(" ","").lower(),infoData['macaddress'].replace(":","").lower(), infoData['datetime'].strftime('%Y-%m-%d')), body=infoData)
            if "result" in res:
                if res['result'] == "created":
                    return True
            return False
        except Exception as err:
            print("Caught exception while trying to save to ES")
            print(err)
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
                    self.sendSMSMessage("Error communicating with %s. Re-running discovery." % device.name, self.notificationNumber)
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
                self.sendSMSMessage("%s is off! Turning it back on!" % device.name, self.notificationNumber)
                print("%s is off! Turning it back on!" % device.name)
                device.on()
                time.sleep(1)
                if device.get_state(True) == 0:
                    if flipped <= 3:
                        flipped += 1
                        time.sleep(1)
                        self.alwaysOnDevice(device, flipped=flipped)
                    else:
                        self.sendSMSMessage("%s is still off. Unable to turn it back on!" % device.name, self.notificationNumber)
                        print("%s is still off. Unable to turn it back on!" % device.name)

    def checkAlwaysOn(self):
        for device in self.devices:
            self.alwaysOnDevice(device)

        for device in self.alwaysOnDevices:
            if not any(x.name == device for x in self.devices):
                try:
                    print("OH MY GOD %s IS MISSING!" % device)
                    self.sendSMSMessage("%s not found in device list. Re-running discovery." % device.name,
                                        self.notificationNumber)
                    self.discovery()
                except AttributeError as err:
                    print("Weird error when trying to check always on. Device likely isn't a device?")
                    print(err)
                    self.discovery()


    def update(self):
        while self.bgRun:
            self.reDiscover()
            self.collectDeviceInfo()
            self.checkAlwaysOn()
            time.sleep(15)