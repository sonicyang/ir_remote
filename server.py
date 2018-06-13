from flask import Flask
from flask_restful import Resource, Api, reqparse
from contextlib import suppress
import subprocess
from functools import reduce
import _thread
import socket
import time

app = Flask(__name__)
api = Api(app)

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

def create_resources():
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
        if subprocess.call(["irsend", "SEND_ONCE", remote_name, key_name]):
            return "FAILED", 500
        else:
            return "OK", 200

class AC(Resource):
    def __send_ir_command__(self):
        pre_bytes = [0b11000100, 0b11010011, 0b01100100, 0b10000000, 0b00000000]
        data_bytes = [None] * 8
        crc = 0

        power = ac_stat["power"]
        temp = ac_stat["temp"]
        mode = ac_stat["mode"]
        speed = ac_stat["speed"]
        direction = ac_stat["dir"]

        if power == "on":
            data_bytes[0] = 0b00100100
        elif power == "off":
            data_bytes[0] = 0b00000100

        data_bytes[2] = int('{0:04b}'.format(31 - temp)[2:][::-1] + "0000", 2)

        if mode == "dry":
            data_bytes[1] = 0b01000000
            data_bytes[2] = 0b11100000 # dry use fix value on temp
        elif mode == "heat":
            data_bytes[1] = 0b10000000
        elif mode == "cool":
            data_bytes[1] = 0b11000000

        data_bytes[3] = 0b00000000
        if speed == "1":
            data_bytes[3] |= 0b01000000
        elif speed == "2":
            data_bytes[3] |= 0b11000000
        elif speed == "3":
            data_bytes[3] |= 0b10100000

        if direction != "auto":
            data_bytes[3] |= int('{0:03b}'.format(int(direction))[::-1] + "00", 2)

        data_bytes[4] = data_bytes[5] = data_bytes[6] = data_bytes[7] = 0

        payload = pre_bytes + data_bytes
        crc = reduce(lambda x, y: x + y, map(lambda x: int(x[::-1], 2), map(lambda x: '{0:08b}'.format(x), payload)))
        # crc = int([-8:][::-1], 2)
        crc = bin(crc)[2:].zfill(8)
        crc = int(crc[-8:], 2)

        payload += [crc]
        print(list(map(lambda x: '{0:08b}'.format(x), payload)))
        pre_flat = "0x" + reduce(lambda x, y: x + y, map(lambda z: '{0:02x}'.format(z), payload[:5]))
        flat = "0x" + reduce(lambda x, y: x + y, map(lambda z: '{0:02x}'.format(z), payload[5:-1]))
        post_flat = "0x" + reduce(lambda x, y: x + y, map(lambda z: '{0:02x}'.format(z), payload[-1:]))

        with open("/etc/lirc/lircd.conf.d/AC.lircd.conf", "w") as fil:
            fil.write("""
begin remote

   name  ac
   bits           64
   flags SPACE_ENC|CONST_LENGTH
   eps            30
   aeps          100

   header       3500  1700
   one           450  1250
   zero          450   450
   pre_data_bits   40
   pre_data       0xC4D3648000
   post_data_bits   8
   post_data       """ + post_flat + """
   ptrail 450
   gap          500000
   toggle_bit_mask 0x0
   frequency    38000

       begin codes
           key_unknown              """ + flat + """
       end codes

end remote
                    """)

        subprocess.call(["service", "lircd", "restart"])
        if not subprocess.call(["irsend", "SEND_ONCE", "ac", "key_unknown"]):
            return True
        else:
            return False

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
