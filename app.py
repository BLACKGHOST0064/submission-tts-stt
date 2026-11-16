import base64
import io
import os
import shutil
import subprocess
import tempfile

from flask import Flask, redirect, render_template, request, url_for
import speech_recognition as sr
from gtts import gTTS

app = Flask(__name__)

NATIVE_AUDIO_EXTS = {".wav", ".aiff", ".aif", ".flac"}


def get_ffmpeg_path():
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/voice-to-text", methods=["GET", "POST"])
def voice_to_text():
    if request.method == "GET":
        return redirect(url_for("index"))

    uploaded_file = request.files.get("audio")
    if not uploaded_file or not uploaded_file.filename:
        return render_template("index.html", stt_error="Please choose an audio file.")

    _, ext = os.path.splitext(uploaded_file.filename)
    ext = ext.lower()

    temp_input_path = None
    temp_wav_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_in:
            uploaded_file.save(tmp_in.name)
            temp_input_path = tmp_in.name

        audio_path = temp_input_path

        if ext not in NATIVE_AUDIO_EXTS:
            ffmpeg_path = get_ffmpeg_path()
            if not ffmpeg_path:
                return render_template(
                    "index.html",
                    stt_error=(
                        f"Format '{ext or 'unknown'}' is not supported without ffmpeg. "
                        "Please upload a .wav, .flac, or .aiff file."
                    ),
                )

            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
                temp_wav_path = tmp_wav.name

            subprocess.run(
                [ffmpeg_path, "-y", "-i", temp_input_path, temp_wav_path],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            audio_path = temp_wav_path

        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)

        text_result = recognizer.recognize_google(audio_data)
        return render_template("index.html", stt_result=text_result)

    except sr.UnknownValueError:
        return render_template("index.html", stt_error="Could not understand the audio.")
    except sr.RequestError as exc:
        return render_template("index.html", stt_error=f"Speech recognition service error: {exc}")
    except subprocess.CalledProcessError:
        return render_template("index.html", stt_error="Failed to convert the uploaded audio file.")
    except Exception as exc:
        return render_template("index.html", stt_error=f"Error processing audio: {exc}")
    finally:
        for path in (temp_input_path, temp_wav_path):
            if path and os.path.exists(path):
                os.remove(path)


@app.route("/text-to-speech", methods=["GET", "POST"])
def text_to_speech():
    if request.method == "GET":
        return redirect(url_for("index"))

    text = request.form.get("text", "").strip()
    if not text:
        return render_template("index.html", tts_error="Please enter some text.")

    try:
        mp3_buffer = io.BytesIO()
        tts = gTTS(text=text, lang="en")
        tts.write_to_fp(mp3_buffer)

        audio_b64 = base64.b64encode(mp3_buffer.getvalue()).decode("ascii")
        return render_template("index.html", tts_text=text, audio_b64=audio_b64)
    except Exception as exc:
        return render_template("index.html", tts_text=text, tts_error=f"Error generating speech: {exc}")


if __name__ == "__main__":
    app.run(debug=False)