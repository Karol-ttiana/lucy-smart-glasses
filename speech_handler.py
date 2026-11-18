import pyttsx3
import threading
import queue
import subprocess
import config
import os
import tempfile


class SpeechHandler:
    """Handles text-to-speech output using various TTS engines"""
    
    def __init__(self):
        self.engine = None
        self.speech_queue = queue.Queue()
        self.speaking = False
        self.speech_thread = None
        self.running = False
        self.tts_engine = config.TTS_ENGINE
        self.use_espeak = False
        
    def initialize(self) -> bool:
        try:
            if self.tts_engine == "festival":
                if self._init_festival():
                    return True
                self.tts_engine = "pyttsx3"
            
            if self.tts_engine == "pyttsx3":
                if self._init_pyttsx3():
                    return True
                self.tts_engine = "espeak"
            
            if self.tts_engine == "espeak":
                return self._init_espeak()
            
            return False
                
        except:
            return False
    
    def _init_festival(self) -> bool:
        try:
            result = subprocess.run(['festival', '--version'], capture_output=True, text=True)
            if result.returncode != 0:
                return False
            
            self.running = True
            self.speech_thread = threading.Thread(target=self._festival_loop, daemon=True)
            self.speech_thread.start()
            
            print("Speech handler (Festival) initialized")
            return True
            
        except:
            return False
    
    def _init_pyttsx3(self) -> bool:
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', config.TTS_RATE)
            
            self.running = True
            self.speech_thread = threading.Thread(target=self._pyttsx3_loop, daemon=True)
            self.speech_thread.start()
            
            print("Speech handler (pyttsx3) initialized")
            return True
            
        except:
            return False
    
    def _init_espeak(self) -> bool:
        try:
            result = subprocess.run(['espeak', '--version'], capture_output=True)
            if result.returncode != 0:
                return False
            
            self.running = True
            self.speech_thread = threading.Thread(target=self._espeak_loop, daemon=True)
            self.speech_thread.start()
            
            print("Speech handler (espeak) initialized")
            return True
            
        except:
            return False
    
    def _festival_loop(self):
        while self.running:
            try:
                text = self.speech_queue.get(timeout=0.5)
                if text:
                    self.speaking = True
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                        f.write(text)
                        temp_file = f.name
                    
                    subprocess.run(['festival', '--tts', temp_file])
                    os.remove(temp_file)
                    self.speaking = False
            except queue.Empty:
                continue
            except:
                self.speaking = False
    
    def _pyttsx3_loop(self):
        while self.running:
            try:
                text = self.speech_queue.get(timeout=0.5)
                if text:
                    self.speaking = True
                    self.engine.say(text)
                    self.engine.runAndWait()
                    self.speaking = False
            except queue.Empty:
                continue
            except:
                self.speaking = False
    
    def _espeak_loop(self):
        while self.running:
            try:
                text = self.speech_queue.get(timeout=0.5)
                if text:
                    self.speaking = True
                    subprocess.run(['espeak', '-v', config.ESPEAK_VOICE, '-s', str(config.TTS_RATE), text])
                    self.speaking = False
            except queue.Empty:
                continue
            except:
                self.speaking = False
    
    def speak(self, text: str, interrupt: bool = False):
        if interrupt:
            while not self.speech_queue.empty():
                try:
                    self.speech_queue.get_nowait()
                except queue.Empty:
                    break
        
        self.speech_queue.put(text)
    
    def is_speaking(self) -> bool:
        return self.speaking
    
    def play_beep(self, frequency: int = 800, duration: float = 0.15):
        try:
            os.system(f'(speaker-test -t sine -f {frequency} >/dev/null 2>&1) & pid=$! ; sleep {duration} ; kill -9 $pid >/dev/null 2>&1')
        except:
            pass
    
    def wait_until_done_speaking(self):
        import time
        while self.is_speaking():
            time.sleep(0.1)
    
    def stop(self):
        self.running = False
        if self.speech_thread:
            self.speech_thread.join(timeout=2.0)
        if self.engine and not self.use_espeak:
            self.engine.stop()
        print("Speech handler stopped")


class SpeechRecognizer:
    """Handles speech-to-text recognition using Groq Whisper API or local Whisper"""
    
    def __init__(self):
        self.model = None
        self.use_groq_whisper = config.USE_GROQ_WHISPER
        self.use_whisper = config.USE_WHISPER
        self.groq_client = None
        
    def initialize(self) -> bool:
        if self.use_groq_whisper:
            if self._init_groq_whisper():
                return True
            self.use_groq_whisper = False
            self.use_whisper = True
        
        if self.use_whisper:
            return self._init_whisper()
        
        return False
    
    def _init_groq_whisper(self) -> bool:
        try:
            from groq import Groq
            
            if not config.GROQ_API_KEY:
                return False
            
            self.groq_client = Groq(api_key=config.GROQ_API_KEY)
            
            print("Groq Whisper API initialized")
            return True
            
        except:
            return False
    
    def _init_whisper(self) -> bool:
        try:
            import whisper
            
            self.model = whisper.load_model(config.WHISPER_MODEL)
            
            print(f"Whisper initialized (model: {config.WHISPER_MODEL})")
            return True
            
        except:
            return False
    
    def listen(self, timeout: int = 10, interrupt_callback=None) -> str:
        if self.use_groq_whisper and self.groq_client:
            return self._listen_groq_whisper(timeout, interrupt_callback)
        elif self.use_whisper and self.model:
            return self._listen_whisper(timeout, interrupt_callback)
        return ""
    
    def _listen_groq_whisper(self, timeout: int, interrupt_callback=None) -> str:
        try:
            import pyaudio
            import numpy as np
            import wave
            import time
            
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024
            )
            
            frames = []
            silence_threshold = 500
            silence_duration = 1.5
            min_audio_duration = 0.5
            
            start_time = time.time()
            last_sound_time = start_time
            recording_started = False
            
            while True:
                if interrupt_callback and interrupt_callback():
                    break
                
                if time.time() - start_time > timeout:
                    break
                
                data = stream.read(1024, exception_on_overflow=False)
                frames.append(data)
                
                audio_data = np.frombuffer(data, dtype=np.int16)
                volume = np.abs(audio_data).mean()
                
                if volume > silence_threshold:
                    last_sound_time = time.time()
                    recording_started = True
                
                if recording_started and (time.time() - last_sound_time > silence_duration):
                    if time.time() - start_time > min_audio_duration:
                        break
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            if len(frames) == 0:
                return ""
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_filename = f.name
                wf = wave.open(temp_filename, 'wb')
                wf.setnchannels(1)
                wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wf.setframerate(16000)
                wf.writeframes(b''.join(frames))
                wf.close()
            
            try:
                with open(temp_filename, "rb") as audio_file:
                    transcription = self.groq_client.audio.transcriptions.create(
                        file=(temp_filename, audio_file.read()),
                        model="whisper-large-v3-turbo",
                        response_format="text",
                        language="en"
                    )
                
                os.unlink(temp_filename)
                return transcription.strip() if transcription else ""
                
            except:
                if os.path.exists(temp_filename):
                    os.unlink(temp_filename)
                return ""
                
        except:
            return ""
    
    def _listen_whisper(self, timeout: int, interrupt_callback=None) -> str:
        try:
            import pyaudio
            import numpy as np
            import wave
            import time
            
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024
            )
            
            frames = []
            silence_threshold = 500
            silence_duration = 1.5
            
            start_time = time.time()
            last_sound_time = start_time
            recording_started = False
            
            while True:
                if interrupt_callback and interrupt_callback():
                    break
                
                if time.time() - start_time > timeout:
                    break
                
                data = stream.read(1024, exception_on_overflow=False)
                frames.append(data)
                
                audio_data = np.frombuffer(data, dtype=np.int16)
                volume = np.abs(audio_data).mean()
                
                if volume > silence_threshold:
                    last_sound_time = time.time()
                    recording_started = True
                
                if recording_started and (time.time() - last_sound_time > silence_duration):
                    break
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            if len(frames) == 0:
                return ""
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_filename = f.name
                wf = wave.open(temp_filename, 'wb')
                wf.setnchannels(1)
                wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wf.setframerate(16000)
                wf.writeframes(b''.join(frames))
                wf.close()
            
            try:
                result = self.model.transcribe(temp_filename, language="en")
                os.unlink(temp_filename)
                return result["text"].strip() if result and "text" in result else ""
            except:
                if os.path.exists(temp_filename):
                    os.unlink(temp_filename)
                return ""
                
        except:
            return ""
