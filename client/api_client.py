from pathlib import Path
from typing import Optional

import requests

DEFAULT_SERVER_URL = "http://localhost:8000"


class ApiClient:
    def __init__(self, base_url: str = DEFAULT_SERVER_URL):
        self.base_url = base_url.rstrip("/")

    def set_server_url(self, url: str):
        self.base_url = url.rstrip("/")

    def get_processing_types(self) -> list:
        r = requests.get(f"{self.base_url}/processing-types", timeout=10)
        r.raise_for_status()
        return r.json()

    def upload_audio(
        self,
        file_path: str,
        processing_type: str,
        speed: Optional[float] = None,
        bitrate: Optional[str] = None,
        output_format: Optional[str] = None,
    ) -> dict:
        path = Path(file_path)
        with open(path, "rb") as f:
            files = {"file": (path.name, f)}
            data = {"processing_type": processing_type}
            if speed is not None:
                data["speed"] = str(speed)
            if bitrate is not None:
                data["bitrate"] = bitrate
            if output_format is not None:
                data["output_format"] = output_format

            r = requests.post(
                f"{self.base_url}/audios/upload", files=files, data=data, timeout=300
            )
        r.raise_for_status()
        return r.json()

    def list_audios(self) -> list:
        r = requests.get(f"{self.base_url}/audios", timeout=15)
        r.raise_for_status()
        return r.json()

    def get_audio(self, audio_id: str) -> dict:
        r = requests.get(f"{self.base_url}/audios/{audio_id}", timeout=15)
        r.raise_for_status()
        return r.json()

    def delete_audio(self, audio_id: str) -> dict:
        r = requests.delete(f"{self.base_url}/audios/{audio_id}", timeout=15)
        r.raise_for_status()
        return r.json()

    def original_url(self, audio_id: str) -> str:
        return f"{self.base_url}/audios/{audio_id}/original"

    def processed_url(self, audio_id: str) -> str:
        return f"{self.base_url}/audios/{audio_id}/processed"

    def download_to(self, url: str, dest_path: Path) -> Path:
        r = requests.get(url, timeout=300)
        r.raise_for_status()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(r.content)
        return dest_path
