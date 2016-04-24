
import helper
import authorization
import alexa_communication
import alexa_audio

import threading
import time


def get_context():
    # Get context for the device (basically a status)
    # TODO eventually make this dynamic and actually reflect the device's state
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


class AlexaDevice:
    def __init__(self, config):
        self.alexa_audio_instance = alexa_audio.AlexaAudio()
        self.config = config
        # self.alexa = None

        self.device_stop_event = threading.Event()
        self.device_thread = threading.Thread(target=self.device_thread_function)
        self.device_thread.start()

    def device_thread_function(self):
        # Start connection
        self.alexa = alexa_communication.AlexaConnection(config, context_handle=get_context)

        # Start user_input_Thread
        threading.Thread(target=self.user_input_thread).start()

        # Connection loop
        while not self.device_stop_event.is_set():
            # Do any device related things here
            time.sleep(0.1)
            pass

        # When complete (stop event is same as user_input_thread
        # Close the alexa connection and set stop event
        self.alexa.close()
        self.device_stop_event.set()
        print("Closing Thread")
        # TODO
        # If anything went wrong, and stop event is not set
        # Start new thread automatically

    def user_input_thread(self):
        # While the stop event is not set
        while not self.device_stop_event.is_set():
            # Prompt user to press enter to start a recording, or q to quit
            text = input("Press enter anytime to start recording (or 'q' to quit).")
            # If 'q' is pressed
            if text == 'q':
                # Set stop event and break out of loop
                self.device_stop_event.set()
                break

            # If enter was pressed (and q was not)
            # Get raw audio from the microphone
            raw_audio = self.alexa_audio_instance.get_audio()
            if raw_audio is None:
                continue

            # TODO make it so that this starts a thread, so the response can be interrupted by user
            stream_id = self.alexa.start_recognize_event(raw_audio)

            self.get_and_process_response(stream_id)

    def get_and_process_response(self, stream_id):
        # Get the response
        response = self.alexa.get_response(stream_id)

        # If no content response
        if response.status == 204:
            return

        # If not ok response status, throw error
        if response.status != 200:
            print(response.read())
            raise NameError("Bad status (%s)" % response.status)

        # Take the response, and parse it
        message = alexa_communication.parse_response(response)

        if 'content' not in message:
            raise KeyError("Content is not available.")
        if len(message['attachment']) > 1:
            raise IndexError("Too many attachments (%d)" % len(message['attachment']))

        # TODO handle multiple attachments received
        attachment = message['attachment'][0]

        # Loop through all content received
        print("%d messages received" % len(message['content']))
        for content in message['content']:
            header = content['directive']['header']

            namespace = header['namespace']
            if namespace == 'SpeechSynthesizer':
                self.directive_speech_synthesizer(content, attachment)
            elif namespace == 'SpeechRecognizer':
                self.directive_speech_recognizer(content, attachment)
            else:
                raise NameError("Namespace not recognized (%s)." % namespace)

    def directive_speech_synthesizer(self, content, attachment):
        header = content['directive']['header']
        payload = content['directive']['payload']

        name = header['name']

        if name == 'Speak':
            # Get token for current TTS object
            token = payload['token']
            audio_response = attachment

            # Set SpeechSynthesizer context state to "playing"
            # TODO add to context
            # Send SpeechStarted Event (with token)
            stream_id = self.alexa.send_event_speech_started(token)
            self.get_and_process_response(stream_id)
            # Play the mp3 file
            self.alexa_audio_instance.play_mp3(audio_response)
            # Send SpeechFinished Event (with token)
            stream_id = self.alexa.send_event_speech_finished(token)
            self.get_and_process_response(stream_id)
            # Set SpeechSynthesizer context state to "finished"

        else:
            raise NameError("Name not recognized (%s)." % name)

    def directive_speech_recognizer(self, content, attachment):
        header = content['directive']['header']
        payload = content['directive']['payload']

        name = header['name']

        if name == 'ExpectSpeech':
            dialog_request_id = header['dialogRequestId']
            timeout = payload['timeoutInMilliseconds']/1000

            raw_audio = self.alexa_audio_instance.get_audio(timeout)
            if raw_audio is None:
                print("Speech timeout.")
                stream_id = self.alexa.send_event_expect_speech_timed_out()
                self.get_and_process_response(stream_id)
                return
            stream_id = self.alexa.start_recognize_event(raw_audio, dialog_request_id=dialog_request_id)

            self.get_and_process_response(stream_id)


    def close(self):
        self.alexa_audio_instance.close()

    def wait_until_close(self):
        self.device_thread.join()


if __name__ == "__main__":
    # Load configuration file
    config = helper.read_dict('config.dict')
    # Check for authorization, if none, initialize
    if 'refresh_token' not in config:
        print("Please go to http://localhost:5000")
        authorization.get_authorization()
        config = helper.read_dict('config.dict')
    # config contains the authorization for the user and device information

    # Create alexa device
    alexa_device = AlexaDevice(config)
    # Wait until device is done before continuing
    alexa_device.wait_until_close()
    # Once done, close
    alexa_device.close()

    print("Done")
