from flask import Flask
from flask_restful import Resource, Api, reqparse
from contextlib import suppress
import subprocess
from functools import reduce
import _thread
import socket
import time

from hvac_ircontrol.ir_sender import LogLevel
from hvac_ircontrol.mitsubishi import Mitsubishi, ClimateMode, FanMode, VanneVerticalMode, AreaMode

app = Flask(__name__)
api = Api(app)

lirc_stat = subprocess.call(["service", "lircd", "status"])
remotes = {}
ac_stat = {}
ac_stat_range = {}

ac_parser = reqparse.RequestParser()

def __add_stat__(stat, default, srange):
    ac_stat[stat] = default
    ac_stat_range[stat] = srange
    ac_parser.add_argument(stat)

__add_stat__("power", "off", ["on", "off"])
__add_stat__("mode", "dry", ["dry", "heat", "cool"])
__add_stat__("temp", 26, ["up", "down"])
__add_stat__("speed", "auto", ["auto", "1", "2", "3"])
__add_stat__("dir", "auto", ["auto", "1", "2", "3", "4", "5"])

def get_IP():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

work = True
def server_broadcaster():
    global work
    IP = get_IP()

    broadcastSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    broadcastSocket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    broadcastSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    while work:
        broadcastSocket.sendto(str(IP).encode("UTF-8"), ('<broadcast>', 10000))
        time.sleep(5)

def start_lirc():
    if lirc_stat == 3:
        subprocess.call(["service", "lircd", "start"])
        lirc_stat = 0

def stop_lirc():
    if lirc_stat == 0:
        subprocess.call(["service", "lircd", "stop"])
        lirc_stat = 3

def create_resources():
    start_lirc()
    try:
        raw_remote_list = subprocess.check_output(["irsend", "LIST", '', '']).decode("UTF-8").split("\n")
        remote_list = list(filter(lambda y: y != "", filter(lambda x: x != "devinput", raw_remote_list)))

        for remote in remote_list:
            raw_cmds = filter(lambda x: x != "", subprocess.check_output(["sudo", "irsend", "LIST", remote, ""]).decode("UTF-8").split("\n"))
            cmd_list = list(map(lambda x: x.split(" ")[1], raw_cmds))

            remotes[remote] = cmd_list
    except Exception:
        return False
    return True

class RemoteList(Resource):
    def get(self):
        return remotes

class Remote(Resource):
    def put(self, remote_name, key_name):
        start_lirc()

        if subprocess.call(["irsend", "SEND_ONCE", remote_name, key_name]):
            return "FAILED", 500
        else:
            return "OK", 200

class AC(Resource):
    def __send_ir_command__(self):
        power = ac_stat["power"]
        temp = ac_stat["temp"]
        mode = ac_stat["mode"]
        speed = ac_stat["speed"]
        direction = ac_stat["dir"]

        if mode == "dry":
            cm = ClimateMode.Dry
        elif mode == "heat":
            cm = ClimateMode.Hot
        elif mode == "cool":
            cm = ClimateMode.Cold

        if speed == "auto":
            sp = FanMode.Auto
        elif speed == "1":
            sp = FanMode.Speed1
        elif speed == "2":
            sp = FanMode.Speed2
        elif speed == "3":
            sp = FanMode.Speed3

        if direction == "auto":
            dr = VanneVerticalMode.Auto
        elif direction == "1":
            dr = VanneVerticalMode.Top
        elif direction == "2":
            dr = VanneVerticalMode.MiddleTop
        elif direction == "3":
            dr = VanneVerticalMode.Middle
        elif direction == "4":
            dr = VanneVerticalMode.MiddleDown
        elif direction == "5":
            dr = VanneVerticalMode.Down

        stop_lirc()

        HVAC = Mitsubishi(17, LogLevel.ErrorsOnly)
        if power == "on":
            HVAC.send_command(
                climate_mode=cm,
                temperature=temp,
                fan_mode=sp,
                vanne_vertical_mode=dr
                )
        elif power == "off":
            HVAC.power_off()

        return True

    def get(self):
        return ac_stat

    def put(self):
        args = ac_parser.parse_args()
        for key in args:
            if key == "temp":
                continue
            value = args[key]
            if value == None:
                continue
            if value in ac_stat_range[key]:
                ac_stat[key] = value
            else:
                return "FAILED", 403

        if args["temp"] == "up":
            if ac_stat["temp"] < 30:
                ac_stat["temp"] += 1
        elif args["temp"] == "down":
            if ac_stat["temp"] > 16:
                ac_stat["temp"] -= 1

        if self.__send_ir_command__():
            return ac_stat, 200
        else:
            return "FAILED", 500


api.add_resource(RemoteList, '/remote_list')
api.add_resource(Remote, '/remote/<string:remote_name>/<string:key_name>')
api.add_resource(AC, '/ac')

if __name__ == '__main__':
    _thread.start_new_thread(server_broadcaster, ())
    if not create_resources():
        print("Failed to construct a list of remotes")
        exit(1)
    app.run(host="0.0.0.0", debug=True)
    work = False
