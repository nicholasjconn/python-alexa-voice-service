
import pyaudio
import wave
import subprocess
import speech_recognition


class AlexaAudio:
    def __init__(self):
        # Initialize pyaudio
        self.pyaudio_instance = pyaudio.PyAudio()

    def close(self):
        # Terminate the pyaudio instance
        self.pyaudio_instance.terminate()

    def get_audio(self):
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

    def play_mp3(self, response):
        # Save MP3 data to a file
        with open("response.mp3", 'wb') as f:
            f.write(response)

        # Convert mp3 response to wave (pyaudio doesn't work with MP3 files)
        subprocess.call(['ffmpeg/bin/ffmpeg', '-y', '-i', 'response.mp3', 'response.wav'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

        # Play a wave file directly
        self.play_wav('response.wav')

    def play_wav(self, file):
        # Open wave wave
        wf = wave.open(file, 'rb')
        # Create pyaudio stream
        stream = self.pyaudio_instance.open(
                    format=self.pyaudio_instance.get_format_from_width(wf.getsampwidth()),
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
