#
#
# Clearing omxplayer temporary files sometimes solves the issue,
# sometimes it doesnt...
# sudo rm -rf /tmp/omxplayerdbus*
# 
#

from flask import Flask, request, send_from_directory, render_template
from flask_cors import CORS, cross_origin
from flask_restful import Resource, Api
from json import dumps
from flask_jsonpify import jsonify
from flask_restful import reqparse
import ntplib # pylint: disable=import-error
from time import ctime

from os.path import splitext
import os
import os.path
import sys
import time 
import subprocess
import json
import random
from pathlib import Path
from time import sleep 
import signal
from pysrt import open as srtopen # pylint: disable=import-error

from Player import LushRoomsPlayer
from OmxPlayer import killOmx

mpegOnly = True
mlpOnly = False
allFormats = False

app = Flask(__name__,  static_folder='static')
api = Api(app)


NTP_SERVER = 'ns1.luns.net.uk'
BASE_PATH = "/media/usb/"
MEDIA_BASE_PATH = BASE_PATH + "tracks/" 
BUILT_PATH = None
AUDIO_PATH_TEST_MP4 = "5.1_AAC_Test.mp4"
JSON_LIST_FILE = "content.json"
SETTINGS_FILE = "settings.json"

TEST_TRACK = MEDIA_BASE_PATH + AUDIO_PATH_TEST_MP4
NEW_TRACK_ARRAY = []
NEW_SRT_ARRAY = []

DEFAULT_SETTINGS = {
    "fadeInterval" : "4",
    "roomName" : "?",
    "canPair" : True,
    "format" : "mp4"
}

player = None
paused = None

CORS(app)
# killOmx as soon as the server starts...
killOmx()

# utils

# Kill omx processes on a ctrl+c/program closure
# to mirror the behaviour of vlc and, in turn, to
# be more graceful

def sigint_handler(signum, frame):
    killOmx()
    exit()
 
signal.signal(signal.SIGINT, sigint_handler)

def getInput():
    parser = reqparse.RequestParser()
    parser.add_argument('id', help='error with id')
    parser.add_argument('interval', help='error with interval')
    parser.add_argument('position', help='error with position')
    parser.add_argument('pairhostname', help='error with pairHostname')
    args = parser.parse_args()
    return args

def printOmxVars():
    print("OMXPLAYER_LIB" in os.environ)
    print("LD_LIBRARY_PATH" in os.environ)
    print("OMXPLAYER_BIN" in os.environ)

def loadSettings():
    # return a graceful error if contents.json can't be found
    
    settingsPath = BASE_PATH + SETTINGS_FILE

    # If no settings.json exists, either rclone hasn't
    # finished yet or something else is wrong...
    if os.path.isfile(settingsPath) == False: 
        return DEFAULT_SETTINGS  
         
    with open(settingsPath) as data: 
        settings = json.load(data)

    settings["roomName"] = settings["name"]

    print("Room name: ", settings["name"]) 
       
    return settings
    
# serve the angular app

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists("static/" + path):
        return send_from_directory('static/', path)
    else:
        return send_from_directory('static/', 'index.html')

# API endpoints

class GetSettings(Resource):
    def get(self):
        return jsonify(loadSettings())

class GetTrackList(Resource): 
    def get(self): 
        global NEW_TRACK_ARRAY
        global NEW_SRT_ARRAY
        global BUILT_PATH
        global player

        c = ntplib.NTPClient()
        try:
            response = c.request(NTP_SERVER)
            print('\n' + 30*'-')
            print('ntp time: ', ctime(response.tx_time))
            print(30*'-' + '\n')
        except:
            print('Could not get ntp time!')
 
        # return a graceful error if the usb stick isn't mounted
        if os.path.isdir(MEDIA_BASE_PATH) == False:
            return jsonify(1)
        
        BUILT_PATH = MEDIA_BASE_PATH
        args = getInput()
    
        print("track list id: " +  str(args['id']))
        
        try:
            if args['id']:
                if NEW_TRACK_ARRAY:
                    BUILT_PATH += [x['Path'] for x in NEW_TRACK_ARRAY if x['ID'] == args['id']][0] + "/"
                    print(BUILT_PATH[0])
        except:
            return jsonify(2)     

        print('BUILT_PATH: ' + str(BUILT_PATH))
            

        # return a graceful error if contents.json can't be found
        if os.path.isfile(BUILT_PATH + JSON_LIST_FILE) == False: 
            return jsonify(2)   
            
        with open(BUILT_PATH + JSON_LIST_FILE) as data:
            TRACK_ARRAY_WITH_CONTENTS = json.load(data)
            NEW_SRT_ARRAY = TRACK_ARRAY_WITH_CONTENTS

            if mpegOnly: 
                NEW_TRACK_ARRAY = [x for x in TRACK_ARRAY_WITH_CONTENTS if ((x['Name'] != JSON_LIST_FILE) and (splitext(x['Name'])[1].lower() != ".srt") and (splitext(x['Name'])[1].lower() != ".mlp"))]
            elif mlpOnly:
                NEW_TRACK_ARRAY = [x for x in TRACK_ARRAY_WITH_CONTENTS if ((x['Name'] != JSON_LIST_FILE) and (splitext(x['Name'])[1].lower() != ".srt") and (splitext(x['Name'])[1].lower() != ".mp4"))]
            elif allFormats:
                NEW_TRACK_ARRAY = [x for x in TRACK_ARRAY_WITH_CONTENTS if ((x['Name'] != JSON_LIST_FILE) and (splitext(x['Name'])[1].lower() != ".srt"))]


            NEW_SRT_ARRAY = [x for x in TRACK_ARRAY_WITH_CONTENTS if splitext(x['Name'])[1].lower() == ".srt"]
            #print(NEW_TRACK_ARRAY)
            #print( NEW_SRT_ARRAY)
            if player:
                player.setPlaylist(NEW_TRACK_ARRAY) 
            else:
                player = LushRoomsPlayer(NEW_TRACK_ARRAY, MEDIA_BASE_PATH)

            return jsonify(NEW_TRACK_ARRAY)
            
class PlaySingleTrack(Resource):
    def get(self):
        global player
        global paused
        global BUILT_PATH

        args = getInput()

        for track in NEW_TRACK_ARRAY:
            if track["ID"] == args["id"]:
                srtFileName = splitext(track["Path"])[0]+".srt"
                if os.path.isfile(BUILT_PATH + srtFileName):
                    print(srtFileName)
                    subs = srtopen(BUILT_PATH + srtFileName)
                pathToTrack = BUILT_PATH + track["Path"]

        if os.path.isfile(pathToTrack) == False:
            print('Bad file path, will not attempt to play...')
            return jsonify("(Playing) File not found!")
 
        print("Playing: " + pathToTrack)
            
        duration = player.start(pathToTrack, subs, BUILT_PATH + srtFileName)
            
        return jsonify(duration)

class PlayPause(Resource):
    def get(self):
        global player 
        duration = player.playPause()
        return jsonify(duration) 

class FadeDown(Resource):
    def get(self):
        global player 
        global BUILT_PATH

        args = getInput()
        print('argsid: ', args["id"])
        # print('argsinterval: ', args["interval"])

        for track in NEW_TRACK_ARRAY:
            if track["ID"] == args["id"]:
                srtFileName = splitext(track["Path"])[0]+".srt"
                if os.path.isfile(BUILT_PATH + srtFileName):
                    print(srtFileName)
                    subs = srtopen(BUILT_PATH + srtFileName)
                pathToTrack = BUILT_PATH + track["Path"]

        if os.path.isfile(pathToTrack) == False:
            print('Bad file path, will not attempt to play...')
            return jsonify(1) 

        response = player.fadeDown(pathToTrack, int(args["interval"]),  subs, BUILT_PATH + srtFileName)

        return jsonify(response)

class Seek(Resource):
    def get(self):
        global player 
        global BUILT_PATH

        args = getInput()
        print('position to seek (%%): ', args["position"])
        # print('argsinterval: ', args["interval"])

        response = player.seek(int(args["position"]))
        print('pos: ', response)

        return jsonify(response)

class PlayerStatus(Resource):
    def get(self):
        global player 

        try:
            response = player.getStatus() 
        except: 
            response = 1

        return jsonify(response)

class Pair(Resource):
    def get(self):
        global player

        args = getInput()
        print('Pair with: ', args["pairhostname"])

        try:
            pairRes = player.pair(args["pairhostname"]) 
        except Exception as e:
            print('Exception: ', e)
            pairRes = 1

        return jsonify(pairRes)

class Enslave(Resource):
    def get(self):
        global player

        player.stop()
        player.exit() 

        print('Enslaving, player stopped and exited')

        # set paired to true

        player.setPaired(True)

        return 0

class Command(Resource):
    def get(self):
        global player
        print('Accepting command from master!')

        return 0

class Stop(Resource):
    def get(self):
        global player 

        try:
            response = player.stop()  
        except: 
            response = 1

        return jsonify(response)

# URLs are defined here

api.add_resource(GetTrackList, '/get-track-list')
api.add_resource(PlaySingleTrack, '/play-single-track')
api.add_resource(PlayPause, '/play-pause')
api.add_resource(FadeDown, '/crossfade')
api.add_resource(Seek, '/seek')
api.add_resource(GetSettings, '/settings')
api.add_resource(PlayerStatus, '/status')
api.add_resource(Pair, '/pair')
api.add_resource(Enslave, '/enslave')
api.add_resource(Command, '/command')
api.add_resource(Stop, '/stop')

if __name__ == '__main__':
   app.run(debug=True, port=80, host='0.0.0.0')
