import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QThread, Signal
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QMessageBox,
    QGroupBox,
    QFormLayout,
    QDoubleSpinBox,
)

from api_client import ApiClient, DEFAULT_SERVER_URL


class UploadWorker(QThread):

    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, api: ApiClient, file_path: str, processing_type: str, extra: dict):
        super().__init__()
        self.api = api
        self.file_path = file_path
        self.processing_type = processing_type
        self.extra = extra

    def run(self):
        try:
            result = self.api.upload_audio(
                self.file_path, self.processing_type, **self.extra
            )
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Processamento de Áudio - Cliente")
        self.resize(820, 600)

        self.api = ApiClient(DEFAULT_SERVER_URL)
        self.selected_file: str | None = None
        self.processing_types: list[dict] = []
        self.temp_dir = Path(tempfile.mkdtemp(prefix="audio_client_"))

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        self._build_ui()
        self._load_processing_types()
        self._refresh_history()

    # ------------------------------------------------------------------
    # Construção da UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # Servidor
        server_row = QHBoxLayout()
        server_row.addWidget(QLabel("Servidor:"))
        self.server_edit = QLineEdit(DEFAULT_SERVER_URL)
        server_row.addWidget(self.server_edit)
        connect_btn = QPushButton("Conectar")
        connect_btn.clicked.connect(self._on_connect_server)
        server_row.addWidget(connect_btn)
        root.addLayout(server_row)

        # Seleção de arquivo
        file_group = QGroupBox("Arquivo de áudio")
        file_layout = QVBoxLayout(file_group)
        file_row = QHBoxLayout()
        self.file_label = QLabel("Nenhum arquivo selecionado")
        select_btn = QPushButton("Selecionar arquivo...")
        select_btn.clicked.connect(self._on_select_file)
        file_row.addWidget(select_btn)
        file_row.addWidget(self.file_label, stretch=1)
        file_layout.addLayout(file_row)
        self.info_label = QLabel("")
        file_layout.addWidget(self.info_label)
        root.addWidget(file_group)

        # Processamento
        proc_group = QGroupBox("Processamento")
        proc_form = QFormLayout(proc_group)
        self.processing_combo = QComboBox()
        self.processing_combo.currentIndexChanged.connect(self._on_processing_changed)
        proc_form.addRow("Tipo:", self.processing_combo)

        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.5, 2.0)
        self.speed_spin.setSingleStep(0.1)
        self.speed_spin.setValue(1.5)
        proc_form.addRow("Velocidade (0.5–2.0):", self.speed_spin)

        self.bitrate_edit = QLineEdit("64k")
        proc_form.addRow("Bitrate (ex: 64k):", self.bitrate_edit)

        self.format_edit = QLineEdit("mp3")
        proc_form.addRow("Formato de saída:", self.format_edit)

        root.addWidget(proc_group)

        send_btn = QPushButton("Enviar e processar")
        send_btn.clicked.connect(self._on_send)
        root.addWidget(send_btn)

        self.status_label = QLabel("")
        root.addWidget(self.status_label)

        # Player
        player_group = QGroupBox("Reprodução")
        player_layout = QHBoxLayout(player_group)
        play_orig_btn = QPushButton("▶ Reproduzir original")
        play_orig_btn.clicked.connect(self._play_original)
        play_proc_btn = QPushButton("▶ Reproduzir processado")
        play_proc_btn.clicked.connect(self._play_processed)
        stop_btn = QPushButton("■ Parar")
        stop_btn.clicked.connect(self.player.stop)
        player_layout.addWidget(play_orig_btn)
        player_layout.addWidget(play_proc_btn)
        player_layout.addWidget(stop_btn)
        root.addWidget(player_group)

        # Histórico
        hist_group = QGroupBox("Histórico")
        hist_layout = QVBoxLayout(hist_group)
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self._on_history_selected)
        hist_layout.addWidget(self.history_list)
        refresh_btn = QPushButton("Atualizar histórico")
        refresh_btn.clicked.connect(self._refresh_history)
        hist_layout.addWidget(refresh_btn)
        root.addWidget(hist_group, stretch=1)

        self.selected_history_audio: dict | None = None

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------
    def _on_connect_server(self):
        self.api.set_server_url(self.server_edit.text().strip())
        self._load_processing_types()
        self._refresh_history()

    def _on_select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar arquivo de áudio",
            "",
            "Áudio (*.mp3 *.wav *.ogg *.flac *.m4a *.aac)",
        )
        if not path:
            return
        self.selected_file = path
        self.file_label.setText(Path(path).name)
        self._show_local_info(path)

    def _show_local_info(self, path: str):
        p = Path(path)
        size_kb = p.stat().st_size / 1024
        self.info_label.setText(
            f"Formato: {p.suffix.lstrip('.').upper()}  |  Tamanho: {size_kb:.1f} KB"
        )

    def _load_processing_types(self):
        try:
            self.processing_types = self.api.get_processing_types()
        except Exception as exc:  # noqa: BLE001
            self.status_label.setText(f"Erro ao conectar ao servidor: {exc}")
            return
        self.processing_combo.clear()
        for item in self.processing_types:
            self.processing_combo.addItem(item["label"], item["key"])

    def _on_processing_changed(self):
        key = self.processing_combo.currentData()
        self.speed_spin.setEnabled(key == "change_speed")
        self.bitrate_edit.setEnabled(key == "reduce_bitrate")
        self.format_edit.setEnabled(key == "convert_format")

    def _on_send(self):
        if not self.selected_file:
            QMessageBox.warning(self, "Aviso", "Selecione um arquivo de áudio primeiro.")
            return
        key = self.processing_combo.currentData()
        if not key:
            QMessageBox.warning(self, "Aviso", "Selecione um tipo de processamento.")
            return

        extra = {}
        if key == "change_speed":
            extra["speed"] = self.speed_spin.value()
        elif key == "reduce_bitrate":
            extra["bitrate"] = self.bitrate_edit.text().strip()
        elif key == "convert_format":
            extra["output_format"] = self.format_edit.text().strip().lstrip(".")

        self.status_label.setText("Enviando e processando...")
        self.worker = UploadWorker(self.api, self.selected_file, key, extra)
        self.worker.finished.connect(self._on_upload_finished)
        self.worker.failed.connect(self._on_upload_failed)
        self.worker.start()

    def _on_upload_finished(self, result: dict):
        self.status_label.setText("Processamento concluído com sucesso.")
        self.selected_history_audio = result
        self._refresh_history()

    def _on_upload_failed(self, error: str):
        self.status_label.setText("Falha no processamento.")
        QMessageBox.critical(self, "Erro", f"Não foi possível processar o áudio:\n{error}")

    def _refresh_history(self):
        try:
            audios = self.api.list_audios()
        except Exception as exc:  # noqa: BLE001
            self.status_label.setText(f"Erro ao carregar histórico: {exc}")
            return
        self.history_list.clear()
        for audio in audios:
            duration = audio.get("duration_sec") or 0
            label = (
                f"{audio['original_name']}  |  {audio['processing_type']}  |  "
                f"{duration:.1f}s  |  {audio['created_at'][:19].replace('T', ' ')}"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, audio)
            self.history_list.addItem(item)

    def _on_history_selected(self, item: QListWidgetItem):
        self.selected_history_audio = item.data(Qt.UserRole)
        audio = self.selected_history_audio
        duration = audio.get("duration_sec") or 0
        self.info_label.setText(
            f"Formato: {audio['original_ext'].lstrip('.').upper()}  |  "
            f"Tamanho: {audio['size_bytes'] / 1024:.1f} KB  |  Duração: {duration:.1f}s"
        )

    # ------------------------------------------------------------------
    # Reprodução
    # ------------------------------------------------------------------
    def _play_original(self):
        if not self.selected_history_audio:
            QMessageBox.information(self, "Info", "Selecione um áudio no histórico primeiro.")
            return
        url = self.api.original_url(self.selected_history_audio["id"])
        self._play_stream(url)

    def _play_processed(self):
        if not self.selected_history_audio:
            QMessageBox.information(self, "Info", "Selecione um áudio no histórico primeiro.")
            return
        url = self.api.processed_url(self.selected_history_audio["id"])
        self._play_stream(url)

    def _play_stream(self, url: str):
        self.player.setSource(QUrl(url))
        self.player.play()


def run():
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    run()
