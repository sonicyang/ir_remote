from flask import Flask
from flask_restful import Resource, Api

import subprocess

app = Flask(__name__)
api = Api(app)

remotes = {}

def create_resources():
    raw_remote_list = subprocess.check_output(["irsend", "LIST", '', '']).decode("UTF-8").split("\n")
    remote_list = list(filter(lambda y: y != "", filter(lambda x: x != "devinput", raw_remote_list)))

    for remote in remote_list:
        raw_cmds = filter(lambda x: x != "", subprocess.check_output(["sudo", "irsend", "LIST", remote, ""]).decode("UTF-8").split("\n"))
        cmd_list = list(map(lambda x: x.split(" ")[1], raw_cmds))

        remotes[remote] = cmd_list

class RemoteList(Resource):
    def get(self):
        return remotes

class Remote(Resource):
    def put(self, remote_name, key_name):
        if subprocess.call(["irsend", "SEND_ONCE", remote_name, key_name]):
            return "", 500
        else:
            return "", 200

api.add_resource(RemoteList, '/remote_list')
api.add_resource(Remote, '/remote/<string:remote_name>/<string:key_name>')

if __name__ == '__main__':
    create_resources()
    app.run(host="0.0.0.0", debug=True)

