
import helper
import authorization
import alexa_communication
import alexa_audio

import threading
import time



def process_resposne(response):
    # Take the response, and parse it
    message = alexa_communication.parse_response(response)

    if 'content' not in message:
        raise KeyError("Content is not available.")

    header = message['content']['directive']['header']
    payload = message['content']['directive']['payload']

    namespace = payload['namespace']
    if namespace == 'SpeechSynthesizer':
        directive_speech_synthesizer(message)
    # elif namespace == 'SpeechRecognizer':
    #     pass
    else:
        raise NameError("Namespace not recognized (%s)." % namespace)


def directive_speech_synthesizer(message):
    header = message['content']['directive']['header']
    payload = message['content']['directive']['payload']

    name = header['name']

    if name == 'Speak':
        # TODO keep track of dialogRequestId and messageId

        # Get token for current TTS object
        token = payload['token']

        # Set SpeechSynthesizer context state to "playing"
        # Send SpeechStarted Event (with token)
        # Play audio
        # Send SpeechFinished Event (with token)
        # Set SpeechSynthesizer context state to "finished"
        pass
    else:
        raise NameError("Name not recognized (%s)." % name)


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
        self.alexa = None

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
            # Set audio, and get mp3 response
            # TODO events and directives related to this should all happen in the same stream
            mp3_response = self.alexa.send_audio_get_response(raw_audio)
            # Play the mp3 file
            self.alexa_audio_instance.play_mp3(mp3_response)

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
