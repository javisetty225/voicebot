import os
import time
import json
import logging
import tempfile
import re
from functools import lru_cache
from typing import List, Dict
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import pipeline
from pydub import AudioSegment

MODEL_NAME = os.getenv("ASR_MODEL", "bofenghuang/whisper-medium-cv11-german")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "25"))
ALLOWED_EXT = {".wav", ".mp3"}
KEYWORDS_PATH = os.getenv("KEYWORDS_PATH", os.path.join(os.path.dirname(__file__), "keywords.json"))
PIPELINE_TASK = "automatic-speech-recognition"

logger = logging.getLogger("voicebot")
logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
keyword_set: set[str] = set()
keywords_raw: List[str] = []
word_pattern = re.compile(r"\b[\wäöüÄÖÜß]+\b", re.UNICODE)

class TranscribeResponse(BaseModel):
    text: str
    keywords: List[str]
    timings: Dict[str, float]

class KeywordsResponse(BaseModel):
    keywords: List[str]

class HealthResponse(BaseModel):
    status: str
    model: str
    device: str

def load_keywords() -> None:
    global keyword_set, keywords_raw
    try:
        with open(KEYWORDS_PATH, encoding="utf-8") as f:
            keywords_raw = json.load(f).get("keywords", [])
        keyword_set = {k.lower() for k in keywords_raw}
        logger.info("Loaded %d keywords", len(keyword_set))
    except Exception:
        logger.exception("Failed to load keywords")
        keyword_set = set()
        keywords_raw = []

@lru_cache(maxsize=1)
def get_asr_pipeline():
    try:
        logger.info("Loading ASR model '%s' on %s", MODEL_NAME, device)
        asr_pipe = pipeline(PIPELINE_TASK, model=MODEL_NAME, device=device)
        try:
            forced = asr_pipe.tokenizer.get_decoder_prompt_ids(language="de", task="transcribe")
            asr_pipe.model.config.forced_decoder_ids = forced
        except Exception:
            logger.warning("Forced decoder ids not set")
        logger.info("ASR model ready")
        return asr_pipe
    except Exception:
        logger.exception("ASR model load failed")
        raise RuntimeError("Model initialization failed")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    load_keywords()
    try:
        get_asr_pipeline()
    except Exception:
        pass  # keep service up for /health
    yield
    # Shutdown (nothing needed now)

app = FastAPI(title="Voicebot ASR", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

def detect_keywords(text: str) -> List[str]:
    found: List[str] = []
    for token in word_pattern.findall(text.lower()):
        if token in keyword_set and token not in found:
            found.append(token)
    return found

def validate_file_meta(upload: UploadFile) -> None:
    ext = os.path.splitext(upload.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="Unsupported file extension")

def ensure_size_limit(size_bytes: int) -> None:
    if size_bytes > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large")

@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", model=MODEL_NAME, device=str(device))

@app.get("/keywords", response_model=KeywordsResponse)
def list_keywords():
    return KeywordsResponse(keywords=sorted(keywords_raw))

@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename")

    validate_file_meta(file)

    start = time.time()
    try:
        contents = await file.read()
        ensure_size_limit(len(contents))

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_path = os.path.join(tmpdir, file.filename)
            with open(raw_path, "wb") as f:
                f.write(contents)

            conv_start = time.time()
            audio = AudioSegment.from_file(raw_path)
            wav_path = os.path.join(tmpdir, "audio.wav")
            audio.export(wav_path, format="wav")
            conv_time = time.time() - conv_start

            asr_start = time.time()
            pipe = get_asr_pipeline()
            result = pipe(wav_path)
            text = result.get("text", "").strip()
            asr_time = time.time() - asr_start

            kw_start = time.time()
            detected = detect_keywords(text)
            kw_time = time.time() - kw_start

        total = time.time() - start
        return TranscribeResponse(
            text=text,
            keywords=detected,
            timings={
                "conversion_sec": round(conv_time, 3),
                "asr_sec": round(asr_time, 3),
                "keyword_sec": round(kw_time, 3),
                "total_sec": round(total, 3),
            },
        )
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=500, detail="Internal Server Error")


