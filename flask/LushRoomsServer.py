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

from LushRoomPlayer import LushRoomPlayer

mpegOnly = True
mlpOnly = False
allFormats = False

app = Flask(__name__,  static_folder='static')
api = Api(app)

MEDIA_BASE_PATH = "/media/usb/tracks/"
BUILT_PATH = None
AUDIO_PATH_TEST_MP4 = "5.1_AAC_Test.mp4"
JSON_LIST_FILE = "content.json"

TEST_TRACK = MEDIA_BASE_PATH + AUDIO_PATH_TEST_MP4
NEW_TRACK_ARRAY = []
NEW_SRT_ARRAY = []


player = None
paused = None

CORS(app)

# utils

def getIdInput():
    parser = reqparse.RequestParser()
    parser.add_argument('id', help='error with id')
    args = parser.parse_args()
    return args

def printOmxVars():
    print("OMXPLAYER_LIB" in os.environ)
    print("LD_LIBRARY_PATH" in os.environ)
    print("OMXPLAYER_BIN" in os.environ)
    
# serve the angular app

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists("static/" + path):
        return send_from_directory('static/', path)
    else:
        return send_from_directory('static/', 'index.html')

# omxplayer callbacks

def posEvent(a, b):
    global player
    print('Position event!' + str(a) + " " + str(b))
    # print('Position: ' + str(player.position()) + "s")
    return

def seekEvent(a, b):
    global player
    print('seek event! ' + str(b))
    return

# API endpoints

class GetTrackList(Resource): 
    def get(self): 
        global NEW_TRACK_ARRAY
        global NEW_SRT_ARRAY
        global BUILT_PATH
        global paused
        global player
        
        BUILT_PATH = MEDIA_BASE_PATH
        args = getIdInput()
        paused = None
        print("track list id: " +  str(args['id']))
        
        if args['id']:
            if NEW_TRACK_ARRAY:
                BUILT_PATH += [x['Path'] for x in NEW_TRACK_ARRAY if x['ID'] == args['id']][0] + "/"
                print(BUILT_PATH[0]) 

        print('BUILT_PATH: ' + str(BUILT_PATH))

        if player:
            player.__del__()
            
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
            player = LushRoomPlayer(NEW_TRACK_ARRAY, MEDIA_BASE_PATH)

            return jsonify(NEW_TRACK_ARRAY)
        
 
class GetSingleTrack(Resource):
    def get(self):
        global NEW_TRACK_ARRAY
        global NEW_SRT_ARRAY
        args = getIdInput()
        print(args['id'])
        for track in NEW_TRACK_ARRAY:
            if track['ID'] == args['id']:
                return jsonify(track["Name"])
            
class PlaySingleTrack(Resource):
    def get(self):
        global player
        global paused
        global BUILT_PATH

        args = getIdInput()
        thisTrack = None
        print('argsid: ', args["id"])
        for track in NEW_TRACK_ARRAY:
            if track["ID"] == args["id"]:
                thisTrack = track
                srtFileName = splitext(track["Path"])[0]+".srt"
                if os.path.isfile(BUILT_PATH + srtFileName):
                    print(srtFileName)
                pathToTrack = BUILT_PATH + track["Path"]
        if os.path.isfile(pathToTrack) == False:
            print('Bad file path, will not attempt to play...')
            return jsonify("(Playing) File not found!")
        print("Playing: " + pathToTrack)

        if findArm():
            
            print('Spawning omx player')
            if (paused == True and paused is not None and player):
                player.action(16) # emulated pause key
                sleep(2.0)
                paused = False
            else:
                # fixed to headphone port for testing
                print('path: ' + str(pathToTrack))
                if player:
                    player.action(16) # emulated play/pause 
                else:
                    # player doesn't exist, spawn a new player
                    player = OMXPlayer(pathToTrack, args=['-w', '-o', 'both'], dbus_name='org.mpris.MediaPlayer2.omxplayer0', pause=True) 
                    player.pause()
                    # omxplayer apparently takes about 2.5 seconds to 'warm up'
                    sleep(2.5)
                    player.positionEvent += posEvent
                    player.seekEvent += seekEvent
                    player.set_position(0)
                    player.play()
                    
            print(str(player.duration()))
            return jsonify(str(player.duration()))
            
            
            # while (player.playback_status() == 'Playing'):
            #     sleep(1)
            #     print(player.position())
        else:
            # just plays the track at the moment. Needs all of the play/pause functionality etc
            print('Spawning vlc player')

            if (paused == True and paused is not None and player):
                player.pause() # emulated pause key
                paused = False
                 
            else:
                vlc_instance = vlc.Instance()
                player = vlc_instance.media_player_new()
                media = vlc_instance.media_new('file://' + pathToTrack)
                player.set_media(media)
                player.play()
                time.sleep(1.5)

            duration = player.get_length() / 1000
            return jsonify(duration)
                       
        return jsonify("(Playing) Neither omxplayer nor vlc have been able to play your track. This needs looking into...")

# Currently seeks foward 10 seconds, works a few times but then comes back
# with something similar to:
#
# /usr/bin/omxplayer: line 67:  2225 Aborted                 LD_LIBRARY_PATH="$OMXPLAYER_LIBS${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" $OMXPLAYER_BIN "$@"
#
# or something even more worrying like:
# 
# *** Error in `/usr/bin/omxplayer.bin': corrupted double-linked list: 0x00d5ed78 ***
# /usr/bin/omxplayer: line 67:  2582 Segmentation fault      LD_LIBRARY_PATH="$OMXPLAYER_LIBS${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" $OMXPLAYER_BIN "$@"
#
# I've tried with as little at 1 second too, the problem remains. Could be
# because the files are so large?
# update, mp4s work a LOT better!
# There seems to be an intermittent issue where dbus loses connection to omxplayer though
# This issue seems to be fixed by including the dbus_name argument when instantiating OMXPlayer, but watch out!

class ScrubFoward(Resource):
    def get(self):
        global player
        # printOmxVars()
        if findArm():
            # scrub the track
            # can_control() always seems to return false...
            #if player.can_control():
            if player.can_seek():
                player.set_position(player.duration()/2.0)
                sleep(0.3)
                return jsonify(player.position())
            return jsonify("Must wait for scrub...")
        return jsonify("(Scrub) You don't seem to be on a media_warrior...")

class PauseTrack(Resource):
    def get(self):
        global player
        global paused
        if findArm():
            # Pause the track
            # Seems to work more robustly than player.pause()
            player.action(16)
            paused = True            
            return jsonify("(omx) Pause successful!")
        else: 
            player.pause() # emulated pause key
            paused = True 
            return jsonify("(vlc) Pause successful!")

        return jsonify("(Pausing error!) You don't seem to be on a LushRoom Pi or a machine with vlc installed...")
        
class StopAll(Resource):
    global player
    def get(self):
        global player
        if findArm():
            # For the moment, kill every omxplayer process
            os.system("killall omxplayer.bin")
            print('omxplayer processes killed!')
            sleep(2.5)
            #if player.can_control():
            #    player.exit()
            return jsonify("omxplayer processes killed")
        return jsonify("(Killing omxplayer proc) You don't seem to be on a media_warrior...")

api.add_resource(GetTrackList, '/get-track-list')
api.add_resource(GetSingleTrack, '/get-single-track')
api.add_resource(PlaySingleTrack, '/play-single-track')
api.add_resource(ScrubFoward, '/scrub-forward')
api.add_resource(PauseTrack, '/pause-track')
api.add_resource(StopAll, '/stop')

if __name__ == '__main__':
   app.run(debug=True, port=80, host='0.0.0.0')
