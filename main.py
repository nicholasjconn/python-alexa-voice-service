
import helper
import authorization
import alexa_communication
import alexa_audio

import threading
import time

__author__ = "NJC"
__license__ = "MIT"
__version__ = "0.1"

def get_context():
    """ Returns the current context of the AlexaDevice.

    See https://developer.amazon.com/public/solutions/alexa/alexa-voice-service/reference/context for more information.

    :return: context dictionary
    """
    # TODO Move into the AlexaDevice object
    # TODO eventually make this dynamic and actually reflect the device's state
    # Get context for the device (basically a status)
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
    """ This object is the AlexaDevice. It uses the AlexaCommunication and AlexaAudio object. The goal is to provide a
        highly abstract yet simple interface for Amazon's Alexa Voice Service (AVS).

    """
    def __init__(self, config):
        """ Initialize the AlexaDevice using the config dictionary. The config dictionary must containing the
            Client_ID, Client_Secret, and refresh_token.

        :param config: config dictionary specific to the device
        """
        self.alexa_audio_instance = alexa_audio.AlexaAudio()
        self.config = config
        # self.alexa = None

        self.device_stop_event = threading.Event()
        self.device_thread = threading.Thread(target=self.device_thread_function)
        self.device_thread.start()

    def device_thread_function(self):
        """ The main thread that waits until the the device is closed. It contains the AlexaConnection object and
            starts any necessary threads for user input.

            Eventually this function will incorporate any device specific functionality.
        """
        # Start connection and save
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
        # TODO If anything went wrong, and stop event is not set, start new thread automatically

    def user_input_thread(self):
        """ This thread initializes a voice recognition event based on user input. This function uses command line
            input for interacting with the user. The user can start a recording, or quit if desired.

            This is currently the "main" thread for the device.
        """
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

            # TODO make it so that this starts a thread, so the response can be interrupted by user if desired
            stream_id = self.alexa.start_recognize_event(raw_audio)

            self.get_and_process_response(stream_id)

    def get_and_process_response(self, stream_id):
        """ For a specified stream_id, get AVS's response and process it. The request must have been sent before calling
            this function.

        :param stream_id: stream_id used for the request
        """
        # Get the response
        response = self.alexa.get_response(stream_id)

        # If no content response, but things are OK, just return
        if response.status == 204:
            return

        # If not OK response status, throw error
        if response.status != 200:
            print(response.read())
            raise NameError("Bad status (%s)" % response.status)

        # Take the response, and parse it
        message = alexa_communication.parse_response(response)

        # If there is no content in the message, throw error (nothing to parse)
        if 'content' not in message:
            raise KeyError("Content is not available.")
        # If there are more than one attachments, throw error (code currently can't handle this.
        # Not sure if this is even possible based on the AVS API.
        if len(message['attachment']) > 1:
            raise IndexError("Too many attachments (%d)" % len(message['attachment']))

        # TODO handle multiple attachments received (not 100% sure multiple attachments can be received)
        attachment = message['attachment'][0]

        # print("%d messages received" % len(message['content']))
        # Loop through all content received
        for content in message['content']:
            header = content['directive']['header']

            # Get the namespace from the header and call the correct process directive function
            namespace = header['namespace']
            if namespace == 'SpeechSynthesizer':
                self.process_directive_speech_synthesizer(content, attachment)
            elif namespace == 'SpeechRecognizer':
                self.process_directive_speech_recognizer(content, attachment)
            # Throw an error in case the namespace is not recognized.
            # This indicates new a process directive function needs to be added
            else:
                raise NameError("Namespace not recognized (%s)." % namespace)

    def process_directive_speech_synthesizer(self, content, attachment):
        """ Process a directive that belongs to the SpeechSynthesizer namespace.

        :param content: content dictionary (contains header and payload)
        :param attachment: attachment included with the content
        """
        header = content['directive']['header']
        payload = content['directive']['payload']

        # Get the name from the header
        name = header['name']

        # Process the SpeechSynthesizer.Speak directive
        if name == 'Speak':
            # Get token for current TTS object
            token = payload['token']
            audio_response = attachment

            # Set SpeechSynthesizer context state to "playing"
            # TODO capture state so that it can be used in context
            # Send SpeechStarted Event (with token)
            stream_id = self.alexa.send_event_speech_started(token)
            self.get_and_process_response(stream_id)
            # Play the mp3 file
            self.alexa_audio_instance.play_mp3(audio_response)
            # Send SpeechFinished Event (with token)
            stream_id = self.alexa.send_event_speech_finished(token)
            self.get_and_process_response(stream_id)
            # Set SpeechSynthesizer context state to "finished"
            # TODO capture state so that it can be used in context
        # Throw an error if the name is not recognized.
        # This indicates new a case needs to be added
        else:
            raise NameError("Name not recognized (%s)." % name)

    def process_directive_speech_recognizer(self, content, attachment):
        """ Process a directive that belongs to the SpeechRecognizer namespace. Attachment not used, but included
            to keep the same arguments as other process_directive functions.

        :param content: content dictionary (contains header and payload)
        :param attachment: attachment included with the content
        """
        header = content['directive']['header']
        payload = content['directive']['payload']

        # Get the name from the header
        name = header['name']

        # Process the SpeechRecognizer.ExpectSpeech directive
        if name == 'ExpectSpeech':
            # Get specific fields for expect speech
            dialog_request_id = header['dialogRequestId']
            timeout = payload['timeoutInMilliseconds']/1000

            # Get audio, as requested by Alexa (using the specified timeout)
            raw_audio = self.alexa_audio_instance.get_audio(timeout)
            # If raw_audio is none, the user did not respond or speak
            if raw_audio is None:
                # TODO add sounds to prompt the user to do something, rather than text
                print("Speech timeout.")
                # Send an event to let Alexa know that the user did not respond
                stream_id = self.alexa.send_event_expect_speech_timed_out()
                self.get_and_process_response(stream_id)
                return

            # Send audio captured (start_recognize_event) using old dialog_request_id and then process reponse
            stream_id = self.alexa.start_recognize_event(raw_audio, dialog_request_id=dialog_request_id)
            self.get_and_process_response(stream_id)
        # Throw an error if the name is not recognized.
        # This indicates new a case needs to be added
        else:
            raise NameError("Name not recognized (%s)." % name)

    def close(self):
        """ Closes the AlexaDevice. Should be called before the program terminates.
        """
        self.alexa_audio_instance.close()

    def wait_until_close(self):
        """ Waits until the user stops the AlexaDevice threads. This uses thread.join() to wait until the thread is
            terminated.
        """
        self.device_thread.join()


if __name__ == "__main__":
    # Load configuration file (contains the authorization for the user and device information)
    config = helper.read_dict('config.dict')
    # Check for authorization, if none, initialize and ask user to go to a website for authorization.
    if 'refresh_token' not in config:
        print("Please go to http://localhost:5000")
        authorization.get_authorization()
        config = helper.read_dict('config.dict')

    # Create alexa device
    alexa_device = AlexaDevice(config)
    # Wait until device is done before continuing
    alexa_device.wait_until_close()
    # Once done, close
    alexa_device.close()

    print("Done")
