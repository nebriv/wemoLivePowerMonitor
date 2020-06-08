import pywemo
import time
import os
import datetime
from flask import Flask, jsonify, render_template, request
import webbrowser
from wemo import Wemo

import configparser
config = configparser.ConfigParser()
config.read('wemo.conf')
app = Flask(__name__, static_folder="templates/assets")
wemo = Wemo(config)

# @app.route('/_data', methods = ['GET'])
# def wemoData():
#     return jsonify(result=wemo.total_power())
#
# @app.route('/_dataHistory', methods = ['GET'])
# def wemoHistory():
#     return jsonify(result=wemo.data_history())
#
# @app.route('/_deviceInfo', methods = ['GET'])
# def deviceInfo():
#     return jsonify(result=wemo.collectDeviceInfo(historyLimit=30))
#
# @app.route('/')
# def index():
#     return render_template('index.html')

# if __name__ == '__main__':
    # app.run()

# start_time = time.time()
# print("Discovering Devices")
# devices = pywemo.discover_devices()
# print(time.time() - start_time)
#

#
# start_time = time.time()
# ips = ["192.168.1.37", "192.168.1.55"]
# print("Connecting to devices")
# devices = []
# for address in ips:
#     port = pywemo.ouimeaux_device.probe_wemo(address)
#     url = 'http://%s:%i/setup.xml' % (address, port)
#     device = pywemo.discovery.device_from_description(url, None)
#     devices.append(device)
# print(time.time() - start_time)
#
# for device in devices:
#     print(device.name)
#     device.update_insight_params()
#     print(device.today_kwh)