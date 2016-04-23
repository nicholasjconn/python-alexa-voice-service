
import helper
import authorization
from communication import AlexaConnection
import communication as alexa_communication

import threading
import time
import pyaudio
import wave
import subprocess
import speech_recognition


def send_audio_get_response(alexa, raw_audio):
    # Set required payload
    payload = {
        "profile": "CLOSE_TALK",
        "format": "AUDIO_L16_RATE_16000_CHANNELS_1"
    }
    # Send the event to alexa
    # TODO make unique_id and dialog_id unique for each request
    stream_id = alexa.send_event('SpeechRecognizer', 'Recognize', 'unique_id2', 'dialog_1',
                                 payload=payload, audio=raw_audio)
    # Get the response
    response = alexa.get_response(stream_id)
    # If not desired response status, throw error
    if response.status != 200:
        print(response.read())
        raise NameError("Bad status (%s)" % response.status)

    # Take the response, and parse it
    message = alexa_communication.parse_response(response)
    # Don't close channel until done parsing response
    response.close()

    # Get audio response from the message attachment
    audio_response = message['attachment']
    # TODO next step is to process each message, not assume what it is
    # print(message['content'])
    # print(len(audio_response))

    return audio_response[0]


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


def device_thread(stop_event, config):
    # Start connection
    alexa = AlexaConnection(config, context_handle=get_context)

    # Start user_input_Thread
    threading.Thread(target=user_input_thread, args=(stop_event, alexa)).start()

    # Connection loop
    while not stop_event.is_set():
        # Do any device related things here
        time.sleep(0.1)
        pass

    # When complete (stop event is same as user_input_thread
    # Close the alexa connection and set stop event
    alexa.close()
    stop_event.set()
    print("Closing Thread")
    # TODO
    # If anything went wrong, and stop event is not set
    # Start new thread automatically


def user_input_thread(stop_event, alexa):
    # While the stop event is not set
    while not stop_event.is_set():
        # Prompt user to press enter to start a recording, or q to quit
        text = input("Press enter anytime to start recording (or 'q' to quit).")
        # If 'q' is pressed
        if text == 'q':
            # Set stop event and break out of loop
            stop_event.set()
            break

        # If enter was pressed (and q was not)
        # Get raw audio from the microphone
        raw_audio = get_audio()
        # Set audio, and get mp3 response
        mp3_response = send_audio_get_response(alexa, raw_audio)
        # Play the mp3 file
        play_mp3(mp3_response)


def start_device_thread(config):
    # Create event used to stop device thread
    device_stop_event = threading.Event()
    # Create and tart the simple device thread
    thread = threading.Thread(target=device_thread, args=(device_stop_event,config))
    thread.start()
    # Return the thread and the stop event
    return device_stop_event, thread


def get_audio():
    # Create a speech recognizer
    r = speech_recognition.Recognizer()
    # Open the microphone (and release is when done using "with")
    with speech_recognition.Microphone() as source:
        # Prompt user to say something
        print("You can start talking now...")
        # Record audio until the user stops talking
        audio = r.listen(source)
    # Convert audio to raw_data (PCM)
    raw_audio = audio.get_raw_data()

    # Rather than recording, read a pre-recorded example (for testing)
    # with open('example_get_time.pcm', 'rb') as f:
    #     raw_audio = f.read()
    return raw_audio


def play_mp3(response):
    # Save MP3 data to a file
    with open("response.mp3", 'wb') as f:
        f.write(response)

    # Convert mp3 response to wave (pyaudio doesn't work with MP3 files)
    subprocess.call(['ffmpeg/bin/ffmpeg', '-y', '-i', 'response.mp3', 'response.wav'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    # Play a wave file directly
    play_wav('response.wav')


def play_wav(file):
    # Open wave wave
    wf = wave.open(file, 'rb')
    # Create pyaudio stream
    stream = pyaudio_instance.open(
                format=pyaudio_instance.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True)

    # Set chunk size for playback
    chunk = 1024

    # Read first chunk of data
    data = wf.readframes(chunk)
    # Continue until there is no data left
    while len(data) > 0:
        stream.write(data)
        data = wf.readframes(chunk)

    # When done, stop stream and close
    stream.stop_stream()
    stream.close()


if __name__ == "__main__":
    # Load configuration file
    config = helper.read_dict('config.dict')
    # Check for authorization, if none, initialize
    if 'refresh_token' not in config:
        print("Please go to http://localhost:5000")
        authorization.get_authorization()
        config = helper.read_dict('config.dict')
    # config contains the authorization for the user and device information

    # Initialize pyaudio
    pyaudio_instance = pyaudio.PyAudio()

    # Start device thread
    device_stop_event, thread = start_device_thread(config)
    # Wait until thread finishes before continuing
    thread.join()

    # Terminate the pyaudio instance
    pyaudio_instance.terminate()

    print("Done")