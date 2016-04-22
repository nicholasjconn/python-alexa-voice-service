
import helper
import authorization

import threading
import time
import json
import requests
from hyper import HTTP20Connection
import pyglet
import os

pyglet.resource.path = [os.path.dirname(os.path.realpath(__file__))]
pyglet.resource.reindex()

#TODO put this and all other communication helper functions in an object
#TODO This will prevent an overrun of global variables

config = {}
latest_token = None
latest_token_time = None

def get_current_token():
    global latest_token, latest_token_time
    # Get current time
    current_time = time.mktime(time.gmtime())
    # If there is no latest token, or the latest token is more than 3570 seconds old
    if (latest_token is None) or (current_time - latest_token_time) > 3570:
        payload = {
            "client_id": config['Client_ID'],
            "client_secret": config['Client_Secret'],
            "refresh_token": config['refresh_token'],
            "grant_type": "refresh_token",
        }
        url = "https://api.amazon.com/auth/o2/token"
        r = requests.post(url, data=payload)
        resp = json.loads(r.text)
        token = resp['access_token']
        # Set new latest token and latest token time
        latest_token = token
        latest_token_time = current_time
    # Otherwise, just use latest token
    else:
        token = latest_token
    return token

def get_context():
    context_audio = {
        "header": {
            "namespace": "AudioPlayer",
            "name": "PlaybackState"
        },
        "payload": {
            "token": "audio_token",
            "offsetInMilliseconds": 0,
            "playerActivity": "IDLE"
        }
    }
    context_speaker = {
        "header": {
        "namespace": "Speaker",
            "name": "VolumeState"
        },
        "payload": {
            "volume": 50,
            "muted": False
        }
    }
    return [context_audio, context_speaker]


def connection_thread(stop_event):
    # Setup connection variables
    url = 'avs-alexa-na.amazon.com'

    # Start connection
    with HTTP20Connection(url, port=443, secure=True, force_proto="h2") as connection:
        # Get directives
        stream_id = send_request(connection, 'GET', '/directives')
        data = connection.get_response(stream_id)
        print(data.status)
        if data.status != 200:
            print(data.read())
            raise NameError("Bad status (%s)" % data.status)
        data.close()

        # Send sync state message
        stream_id = send_event(connection, "System", "SynchronizeState", "unique_id")
        data = connection.get_response(stream_id)
        if data.status != 204:
            print(data.read())
            raise NameError("Bad status (%s)" % data.status)
        data.close()

        with open('example_get_time.pcm', 'rb') as f:
            raw_audio = f.read()
        payload = {
            "profile": "CLOSE_TALK",
            "format": "AUDIO_L16_RATE_16000_CHANNELS_1"
        }
        stream_id = send_event(connection, 'SpeechRecognizer', 'Recognize', 'unique_id2', 'dialog_1',
                               payload=payload,audio=raw_audio)
        data = connection.get_response(stream_id)
        response = data.read()
        voice = response.split(b'\r\n')[-3]
        with open("response.mp3", 'wb') as f:
            f.write(voice)
        player = pyglet.resource.media('response.mp3')
        player.play()
        time.sleep(5)

        # # Connection loop
        # while not stop_event.isSet():
        #     # If timeout is getting close
        #         # Send ping
        #         # If failed ping, close connection (and restart below)
        #     # If there is anything in the queue, send it
        #     # If there is anything to be read from the server, read it
        #     pass

    print("Closing Thread")
    # If anything went wrong, and stop event is not set
        # Start new thread automatically

def send_request(connection, method, path, body=None, boundary='this-is-my-boundary'):
    headers = {
        'authorization': 'Bearer %s' % get_current_token(),
        'content-type': 'multipart/form-data; boundary=%s' % boundary
    }
    path = '/v20160207' + path
    if body is not None:
        stream_id = connection.request(method, path, headers=headers, body=body)
    else:
        stream_id = connection.request(method, path, headers=headers)

    return stream_id


def send_event(connection, namespace, name, message_id, dialog_request_id="", payload={}, audio=None):
    body_dict = {
        "context": get_context(),
        "event": {
            "header": {
                "namespace": namespace,
                "name": name,
                "messageId": message_id,
                "dialogRequestId": dialog_request_id
            },
            "payload": payload
        }
    }

    boundary='$this-is-my-boundary$'

    start_json = """--%s
Content-Disposition: form-data; name="metadata"
Content-Type: application/json; charset=UTF-8\n\n""" % boundary

    start_audio = """--%s
Content-Disposition: form-data; name="audio"
Content-Type: application/octet-stream\n\n""" % boundary

    # Create body string, and add json data
    body_string = (start_json + json.dumps(body_dict) + "--" + boundary).encode()
    # If raw audio exists, add that as well to the body strring
    if audio is not None:
        body_string += ("\n" + start_audio).encode() + audio
    # Add final boundary
    body_string += ("--" + boundary + "--").encode()

    return send_request(connection, 'GET', '/events', body=body_string, boundary=boundary)


def start_connection_thread():
    connection_stop_event = threading.Event()
    thread = threading.Thread(target=connection_thread, args=(connection_stop_event,))
    thread.start()
    return connection_stop_event

if __name__ == "__main__":
    # Load configuration file
    config = helper.read_dict('config.dict')
    # Check for authorization, if none, initialize
    if 'refresh_token' not in config:
        print("Please go to http://localhost:5000")
        authorization.get_authorization()
        config = helper.read_dict('config.dict')
    authorization = config['refresh_token']

    print("DONE!")

    start_connection_thread()

    pass
