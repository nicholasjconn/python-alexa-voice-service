
import time
import json
import requests
import threading
from hyper import HTTP20Connection


def parse_response(response):
    content = response.headers.pop('content-type')[0]
    b_start = content.find(b'boundary=')
    b_end = content[b_start:].find(b';')
    if b_end == -1:
        boundary = content[b_start+9:]
    else:
        boundary = content[b_start+9:b_start+b_end]

    data = response.read()
    message_parts = data.split(b'--'+boundary)
    message_parts = [p for p in message_parts
                     if p != b'--' and p != b'--\r\n' and len(p) != 0]

    # Currently assuming only 0-2 messages per response
    if len(message_parts) > 2:
        raise NameError("Too many messages (%d)!" % len(message_parts))

    message = dict()
    message['content'] = []
    message['attachment'] = []

    # For each message part
    for part in message_parts:
        message_chunk = part.split(b'\r\n\r\n')
        if len(message_chunk) != 2:
            raise NameError("Too many parts to the sub-message! (%s)" % len(message_chunk))
        message_header = message_chunk[0].strip()
        message_content = message_chunk[1].strip()

        # Find start and stop of content-type
        content_type_start = message_header.find(b'Content-Type: ')+14
        content_type_end = message_header[content_type_start:].find(b'\r\n')
        # If no end index was found, just go to the end
        if content_type_end == -1:
            content_type = message_header[content_type_start:]
        else:
            content_type = message_header[content_type_start:content_type_start+content_type_end]

        # Check the content type, should be json or octet
        if content_type == b'application/json; charset=UTF-8':
            message['content'].append(json.loads(message_content.decode()))
        elif content_type == b'application/octet-stream':
            message['attachment'].append(message_content)

    return message


class AlexaConnection:
    def __init__(self, config, context_handle, boundary='this-is-my-boundary'):
        self.latest_token = None
        self.latest_token_time = None
        self.client_id = config['Client_ID']
        self.client_secret = config['Client_Secret']
        self.refresh_token = config['refresh_token']

        self.boundary = boundary
        self.context_handle = context_handle

        self.url = 'avs-alexa-na.amazon.com'
        self.lock = threading.Lock()
        self.ping_stop_event = threading.Event()

        self.init_connection()

    def init_connection(self):
        # Open connection
        self.connection = HTTP20Connection(self.url, port=443, secure=True, force_proto="h2")

        # Start by sending a "GET" /directives
        stream_id = self.send_request('GET', '/directives')
        data = self.get_response(stream_id)
        if data.status != 200:
            print(data.read())
            raise NameError("Bad status (%s)" % data.status)
        data.close()

        # Send sync state message
        stream_id = self.send_event("System", "SynchronizeState", "unique_id")
        data = self.get_response(stream_id)
        if data.status != 204:
            print(data.read())
            raise NameError("Bad status (%s)" % data.status)
        data.close()

        # Start ping thread
        thread = threading.Thread(target=self.ping_thread)
        thread.start()

    def ping_thread(self):
        # Run and wait until ping thread is stopped
        while not self.ping_stop_event.is_set():
            stream_id = self.send_request('GET', '/ping', path_version=False)
            data = self.get_response(stream_id)
            # If ping failed
            if data.status != 204:
                print(data.read())
                print("Ping not successful.")
                # Close connection
                self.lock.acquire()
                self.connection.close()
                self.lock.release()
                # Reinitialize the connection
                self.init_connection()
                break
            start_time = time.mktime(time.gmtime())
            while not self.ping_stop_event.is_set() \
                    and (time.mktime(time.gmtime()) - start_time) < 4*60:
                time.sleep(1)
        print("Closing ping thread.")

    def close(self):
        self.ping_stop_event.set()
        self.lock.acquire()
        self.connection.close()
        self.lock.release()

    def get_current_token(self):
        # Get current time
        current_time = time.mktime(time.gmtime())
        # If there is no latest token, or the latest token is more than 3570 seconds old
        if (self.latest_token is None) or (current_time - self.latest_token_time) > 3570:
            payload = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            }
            url = "https://api.amazon.com/auth/o2/token"
            r = requests.post(url, data=payload)
            resp = json.loads(r.text)
            token = resp['access_token']
            # Set new latest token and latest token time
            self.latest_token = token
            self.latest_token_time = current_time
        # Otherwise, just use latest token
        else:
            token = self.latest_token
        return token

    def send_request(self, method, path, body=None, path_version=True):
        headers = {
            'authorization': 'Bearer %s' % self.get_current_token(),
            'content-type': 'multipart/form-data; boundary=%s' % self.boundary
        }
        if path_version:
            path = '/v20160207' + path

        self.lock.acquire()
        if body is not None:
            stream_id = self.connection.request(method, path, headers=headers, body=body)
        else:
            stream_id = self.connection.request(method, path, headers=headers)
        self.lock.release()

        return stream_id

    def send_event(self, namespace, name, message_id, dialog_request_id="", payload=None, audio=None):
        if payload is None:
            payload = {}
        body_dict = {
            "context": self.context_handle(),
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

        start_json = '--%s\nContent-Disposition: form-data; name="metadata"\n' \
                     'Content-Type: application/json; charset=UTF-8\n\n' % self.boundary

        start_audio = '--%s\nContent-Disposition: form-data; name="audio"\n' \
                      'Content-Type: application/octet-stream\n\n' % self.boundary

        # Create body string, and add json data
        body_string = (start_json + json.dumps(body_dict) + "--" + self.boundary).encode()
        # If raw audio exists, add that as well to the body strring
        if audio is not None:
            body_string += ("\n" + start_audio).encode() + audio
        # Add final boundary
        body_string += ("--" + self.boundary + "--").encode()

        return self.send_request('GET', '/events', body=body_string)

    def get_response(self, stream_id):
        self.lock.acquire()
        result = self.connection.get_response(stream_id)
        self.lock.release()
        return result
