# Python Alexa Voice Service

This project is a Python implementation of Amazon's Alexa Voice Service (AVS). The goal of this project is to create cross-platform example Alexa device that is completely compatible with the current AVS API (v20160207). This is a work in progress.

## Getting Started
Clone the repository and install the necessary prerequisites. The example Alexa device can be started with the following command:

```
python main.py
```

### Requirements
 - Python 3
    - cherrypy
    - requests
    - hyper (developer branch)
    - pyaudio
    - speech_recognition
 - Microphone and speaker

## Cross-Platform

This code has only been tested on Windows. This project will eventually support Linux and hopefully OS X. The final goal is for this project to work out of the box on a Raspberry Pi.

## License
MIT - [See LICENSE](./license.txt)

## Future Work
Please feel free to add functionality or fix any bugs that you find. I will be working on this project whenever I have time, so stay tuned for updates.

Currently, only the SpeechRecognizer and SpeechSynthesizer interfaces are supported. More will be added in the near future.

## Alexa Voice Service

The following link has all of the information needed to understand the Alexa Voice Service API:
https://developer.amazon.com/public/solutions/alexa/alexa-voice-service/content/avs-api-overview
