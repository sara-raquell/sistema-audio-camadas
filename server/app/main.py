import shutil
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from . import models, schemas, processing
from .config import PROCESSING_TYPES
from .database import get_db, init_db

app = FastAPI(title="Sistema de Processamento de Áudio - Atividade 3")

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"}


@app.on_event("startup")
def on_startup():
    init_db()


@app.post("/audios/upload", response_model=schemas.AudioOut)
async def upload_audio(
    file: UploadFile = File(...),
    processing_type: str = Form(...),
    speed: Optional[float] = Form(None),
    bitrate: Optional[str] = Form(None),
    output_format: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    if processing_type not in PROCESSING_TYPES:
        raise HTTPException(400, f"Tipo de processamento inválido: {processing_type}")

    original_ext = Path(file.filename).suffix.lower()
    if original_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Extensão não suportada: {original_ext}")

    audio_id = uuid.uuid4()
    audio_dir = processing.make_audio_dir(str(audio_id))

    # Salva o arquivo original como audio.{ext}
    original_path = audio_dir / f"audio{original_ext}"
    with open(original_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    size_bytes = original_path.stat().st_size

    # Inspeciona o áudio (duração, sample rate, canais, bitrate)
    try:
        info = processing.probe_audio(original_path)
    except processing.ProcessingError as exc:
        raise HTTPException(500, str(exc))

    # Define extensão/formato de saída
    out_ext = f".{output_format}" if (processing_type == "convert_format" and output_format) else original_ext
    processed_path = audio_dir / f"audio_processed{out_ext}"

    params = {"speed": speed, "bitrate": bitrate, "output_format": output_format}
    params = {k: v for k, v in params.items() if v is not None}

    try:
        ffmpeg_cmd = processing.apply_processing(
            original_path, processed_path, processing_type, params
        )
    except processing.ProcessingError as exc:
        raise HTTPException(500, str(exc))

    waveform_path = audio_dir / "waveform.png"
    processing.generate_waveform(original_path, waveform_path)

    processing.write_meta_json(
        audio_dir, original_path, processed_path, processing_type, params, ffmpeg_cmd
    )

    audio = models.Audio(
        id=audio_id,
        original_name=file.filename,
        original_ext=original_ext,
        mime_type=file.content_type,
        size_bytes=size_bytes,
        duration_sec=info["duration_sec"],
        sample_rate=info["sample_rate"],
        channels=info["channels"],
        bitrate=info["bitrate"],
        processing_type=processing_type,
        path_original=str(original_path),
        path_processed=str(processed_path) if processed_path.exists() else None,
    )
    db.add(audio)
    db.commit()
    db.refresh(audio)

    return audio


@app.get("/audios", response_model=List[schemas.AudioOut])
def list_audios(db: Session = Depends(get_db)):
    return db.query(models.Audio).order_by(models.Audio.created_at.desc()).all()


@app.get("/audios/{audio_id}", response_model=schemas.AudioOut)
def get_audio(audio_id: uuid.UUID, db: Session = Depends(get_db)):
    audio = db.query(models.Audio).filter(models.Audio.id == audio_id).first()
    if not audio:
        raise HTTPException(404, "Áudio não encontrado")
    return audio


def _get_audio_or_404(audio_id: uuid.UUID, db: Session) -> models.Audio:
    audio = db.query(models.Audio).filter(models.Audio.id == audio_id).first()
    if not audio:
        raise HTTPException(404, "Áudio não encontrado")
    return audio


@app.get("/audios/{audio_id}/original")
def download_original(audio_id: uuid.UUID, db: Session = Depends(get_db)):
    audio = _get_audio_or_404(audio_id, db)
    if not Path(audio.path_original).exists():
        raise HTTPException(404, "Arquivo original não encontrado em disco")
    return FileResponse(audio.path_original)


@app.get("/audios/{audio_id}/processed")
def download_processed(audio_id: uuid.UUID, db: Session = Depends(get_db)):
    audio = _get_audio_or_404(audio_id, db)
    if not audio.path_processed or not Path(audio.path_processed).exists():
        raise HTTPException(404, "Arquivo processado não encontrado")
    return FileResponse(audio.path_processed)


@app.get("/audios/{audio_id}/waveform")
def download_waveform(audio_id: uuid.UUID, db: Session = Depends(get_db)):
    audio = _get_audio_or_404(audio_id, db)
    waveform_path = Path(audio.path_original).parent / "waveform.png"
    if not waveform_path.exists():
        raise HTTPException(404, "Waveform não encontrada")
    return FileResponse(waveform_path)


@app.delete("/audios/{audio_id}")
def delete_audio(audio_id: uuid.UUID, db: Session = Depends(get_db)):
    audio = _get_audio_or_404(audio_id, db)
    audio_dir = Path(audio.path_original).parent
    processing.move_to_trash(audio_dir)
    db.delete(audio)
    db.commit()
    return {"status": "ok", "detail": "Áudio movido para a lixeira"}


@app.get("/processing-types", response_model=List[schemas.ProcessingTypeOut])
def get_processing_types():
    return [{"key": k, "label": v} for k, v in PROCESSING_TYPES.items()]


@app.get("/", response_class=HTMLResponse)
def web_interface(db: Session = Depends(get_db)):
    audios = db.query(models.Audio).order_by(models.Audio.created_at.desc()).all()

    rows = ""
    for a in audios:
        rows += f"""
        <tr>
            <td>{a.original_name}</td>
            <td>{PROCESSING_TYPES.get(a.processing_type, a.processing_type)}</td>
            <td>{a.duration_sec:.2f}s</td>
            <td>{a.created_at:%d/%m/%Y %H:%M}</td>
            <td><audio controls src="/audios/{a.id}/original"></audio></td>
            <td>
                {"<audio controls src='/audios/" + str(a.id) + "/processed'></audio>" if a.path_processed else "-"}
            </td>
            <td><img src="/audios/{a.id}/waveform" width="200" onerror="this.style.display='none'"/></td>
        </tr>
        """

    html = f"""
    <html>
    <head>
        <title>Áudios Armazenados</title>
        <style>
            body {{ font-family: sans-serif; margin: 2rem; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
            th {{ background: #f0f0f0; }}
        </style>
    </head>
    <body>
        <h1>Áudios armazenados</h1>
        <table>
            <tr>
                <th>Nome original</th><th>Processamento</th><th>Duração</th>
                <th>Data</th><th>Original</th><th>Processado</th><th>Waveform</th>
            </tr>
            {rows}
        </table>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
