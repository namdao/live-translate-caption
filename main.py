import sys
from PyQt6.QtWidgets import QApplication
from src.audio.recorder import Recorder, MicrophoneNotFoundError
from src.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("RealTime Recorder")

    recorder = Recorder()
    window = MainWindow()

    def on_start():
        try:
            recorder.start()
        except MicrophoneNotFoundError as e:
            window.show_error(str(e))

    def on_stop():
        try:
            path = recorder.stop()
            if path:
                window.show_status(f"Saved: {path}")
            else:
                window.show_status("Stopped (no audio recorded)")
        except Exception as e:
            window.show_error(str(e))

    window.recording_started.connect(on_start)
    window.recording_stopped.connect(on_stop)
    window.recording_paused.connect(recorder.pause)
    window.recording_resumed.connect(recorder.resume)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
