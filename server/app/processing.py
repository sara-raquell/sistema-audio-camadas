"""
Funções responsáveis por:
 - inspecionar o áudio recebido (ffprobe)
 - aplicar o processamento solicitado (ffmpeg)
 - gerar a imagem da forma de onda (waveform.png)
 - gravar o arquivo meta.json com informações complementares
"""
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import FFMPEG_BIN, FFPROBE_BIN, STORAGE_DIR, TRASH_DIR


class ProcessingError(Exception):
    pass


def probe_audio(path: Path) -> dict:
    """Executa ffprobe e retorna duração, sample_rate, canais e bitrate."""
    cmd = [
        FFPROBE_BIN,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError as exc:
        raise ProcessingError(
            "ffprobe não encontrado no servidor. Instale o FFmpeg."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise ProcessingError(f"Falha ao inspecionar áudio: {exc.stderr}") from exc

    data = json.loads(result.stdout)
    audio_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "audio"), {}
    )
    fmt = data.get("format", {})

    duration = fmt.get("duration") or audio_stream.get("duration")
    bitrate = fmt.get("bit_rate") or audio_stream.get("bit_rate")

    return {
        "duration_sec": float(duration) if duration else None,
        "sample_rate": int(audio_stream["sample_rate"]) if audio_stream.get("sample_rate") else None,
        "channels": int(audio_stream["channels"]) if audio_stream.get("channels") else None,
        "bitrate": int(bitrate) if bitrate else None,
    }


def file_checksum(path: Path) -> str:
    """Calcula o checksum SHA-256 do arquivo."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def make_audio_dir(audio_id: str) -> Path:
    """Cria a subpasta organizada por data (AAAA/MM/DD) e UUID."""
    today = datetime.utcnow()
    audio_dir = STORAGE_DIR / f"{today:%Y}" / f"{today:%m}" / f"{today:%d}" / audio_id
    audio_dir.mkdir(parents=True, exist_ok=True)
    return audio_dir


def apply_processing(
    input_path: Path,
    output_path: Path,
    processing_type: str,
    params: Optional[dict] = None,
) -> list:
    """
    Aplica o processamento solicitado via FFmpeg.
    Retorna a lista de argumentos usados (para registro em meta.json).
    """
    params = params or {}
    cmd = [FFMPEG_BIN, "-y", "-i", str(input_path)]

    if processing_type == "normalize_volume":
        # Normalização de volume via filtro loudnorm (EBU R128)
        cmd += ["-af", "loudnorm"]

    elif processing_type == "convert_mono":
        cmd += ["-ac", "1"]

    elif processing_type == "change_speed":
        speed = float(params.get("speed", 1.5))
        # atempo aceita 0.5–2.0 por filtro; para valores fora, seria necessário encadear
        cmd += ["-af", f"atempo={speed}"]

    elif processing_type == "reduce_bitrate":
        bitrate = params.get("bitrate", "64k")
        cmd += ["-b:a", str(bitrate)]

    elif processing_type == "convert_format":
        # A extensão de saída já define o formato; nada extra é necessário
        pass

    else:
        raise ProcessingError(f"Tipo de processamento desconhecido: {processing_type}")

    cmd += [str(output_path)]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError as exc:
        raise ProcessingError(
            "ffmpeg não encontrado no servidor. Instale o FFmpeg."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise ProcessingError(f"Falha ao processar áudio: {exc.stderr}") from exc

    return cmd


def generate_waveform(input_path: Path, output_path: Path) -> None:
    """Gera uma imagem PNG com a forma de onda do áudio usando o filtro showwavespic."""
    cmd = [
        FFMPEG_BIN, "-y",
        "-i", str(input_path),
        "-filter_complex", "showwavespic=s=1000x300:colors=#4f8ef7",
        "-frames:v", "1",
        str(output_path),
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        # A waveform é um recurso complementar; não deve derrubar o fluxo principal
        pass


def write_meta_json(
    audio_dir: Path,
    original_path: Path,
    processed_path: Optional[Path],
    processing_type: str,
    processing_params: dict,
    ffmpeg_cmd: Optional[list],
) -> Path:
    """Grava o meta.json com checksum, parâmetros e tamanho dos arquivos."""
    meta = {
        "processing_type": processing_type,
        "processing_params": processing_params,
        "ffmpeg_command": ffmpeg_cmd,
        "original": {
            "path": original_path.name,
            "size_bytes": original_path.stat().st_size,
            "checksum_sha256": file_checksum(original_path),
        },
    }
    if processed_path and processed_path.exists():
        meta["processed"] = {
            "path": processed_path.name,
            "size_bytes": processed_path.stat().st_size,
            "checksum_sha256": file_checksum(processed_path),
        }

    meta_path = audio_dir / "meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    return meta_path


def move_to_trash(audio_dir: Path) -> None:
    """Move uma pasta de áudio inteira para storage/trash/ (exclusão suave)."""
    import shutil
    if not audio_dir.exists():
        return
    destination = TRASH_DIR / audio_dir.name
    shutil.move(str(audio_dir), str(destination))
