import os
import tempfile
import requests
import streamlit as st
from audiorecorder import audiorecorder  # requires: pip install streamlit-audiorecorder

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")

st.title("Voicebot")

def backend_available():
    try:
        r = requests.get(f"{BACKEND_URL}/health", timeout=2)
        return r.ok
    except Exception:
        return False

def display_keywords(keywords):
    if keywords:
        buttons = ' '.join(
            f'<button style="background-color: yellow; padding: 5px; margin: 2px; border: none; border-radius: 5px; cursor: pointer; animation: flash 1.5s infinite;">{k}</button>'
            for k in keywords
        )
        st.markdown(
            f'<div style="display: flex; align-items: center; flex-wrap: wrap;"><strong>Keywords:</strong>&nbsp;{buttons}</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown("Keywords:")

def send_to_backend(file_name, file_obj, mime="application/octet-stream"):
    if not backend_available():
        st.error(f"Backend not reachable at {BACKEND_URL}. Start it or set BACKEND_URL.")
        return
    response = None
    try:
        files = {"file": (file_name, file_obj, mime)}
        response = requests.post(f"{BACKEND_URL}/transcribe", files=files, timeout=30)
        response.raise_for_status()
        data = response.json()
        st.markdown(f"**Transcribed Text:** {data.get('text','')}")
        display_keywords(data.get("keywords", []))
    except requests.exceptions.RequestException as e:
        st.error(f"Request error: {e}")
        if response is not None:
            try:
                st.write(f"Details: {response.json().get('error','Unknown error')}")
            except Exception:
                st.write(f"Raw response: {response.text}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")

st.markdown("### Please upload an audio file or record your audio.")

with st.expander("Upload an Audio File"):
    st.header("Upload an Audio File")
    audio_file = st.file_uploader("Choose an audio file", type=["mp3", "wav"])
    if audio_file:
        st.audio(audio_file)
        send_to_backend(audio_file.name, audio_file, audio_file.type or "application/octet-stream")

st.markdown("---")

with st.expander("Record Audio"):
    st.header("Audio Recorder")
    audio = audiorecorder("Click to record", "Click to stop recording")
    if len(audio) > 0:
        raw_bytes = audio.export().read()
        st.audio(raw_bytes)
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            audio.export(tmp.name, format="wav")
            tmp.seek(0)
            send_to_backend("recording.wav", tmp, "audio/wav")

st.markdown("""
<style>
@keyframes flash {
  0% { background-color: yellow; }
  50% { background-color: lightyellow; }
  100% { background-color: yellow; }
}
</style>
""", unsafe_allow_html=True)
