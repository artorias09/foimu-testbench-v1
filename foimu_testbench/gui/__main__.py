import argparse
from pathlib import Path
from PySide6.QtWidgets import QApplication
from .window import Window
from ..scenarios import Scenario

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Bancada digital FO-IMU')
    parser.add_argument('--port', type=int, default=8877)
    parser.add_argument('--scenario')
    args = parser.parse_args()
    app = QApplication([])
    window = Window(args.port)
    if args.scenario:
        window.load(Scenario.from_json(Path(args.scenario).read_bytes()))
    window.show()
    raise SystemExit(app.exec())
