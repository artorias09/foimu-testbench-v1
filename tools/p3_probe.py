"""Drive the actual Qt controls for local process acceptance."""
import json
from pathlib import Path
import sys
from unittest.mock import patch
from PySide6 import QtCore, QtWidgets
from foimu_testbench.gui.window import Window
from foimu_testbench.scenarios import Scenario


def main(port, directory, mode, source):
    case = Path(directory)
    app = QtWidgets.QApplication([])
    w = Window(int(port))
    w.load(Scenario.from_json((case/'scenario.json').read_bytes()))
    w.out.setText(source)
    w.show()
    started = live = slow = stopped = False
    expected_id = None
    result = {'ok': False, 'qt_platform': app.platformName()}

    def finish():
        result.update(ok=True, live_seen=live, slowed=slow, stopped=stopped, state=w.state,
                      perf=w.perf.copy(), report_opened=w.tabs.currentIndex()==1,
                      shown_report=w.report_view.toPlainText()==w.report,
                      visible_events=len(w.visible), plotted_points=len(w.rows))
        w.grab().save(str(case/'window.png'))
        w.close()

    def tick():
        nonlocal started, live, slow, stopped, expected_id
        if not started and w.start_btn.isEnabled():
            started = True
            if mode in ('open','partial'):
                with patch.object(QtWidgets.QFileDialog,'getExistingDirectory',return_value=source):
                    w.open_btn.click()
            else:
                w.start_btn.click()
        root = Path(source)/'run.json'
        if started and expected_id is None and root.is_file():
            expected_id = json.loads(root.read_bytes())['run_id']
        if not expected_id or w.pending or w.state.get('run_id') != expected_id:
            return
        state = w.state['execution_status']
        if state == 'running' and w.rows and not live:
            live = True
            (case/'active').write_text(expected_id)
            if mode == 'close':
                finish()
                return
            if mode == 'slow':
                slow = True
                w.timer.stop()
                QtCore.QTimer.singleShot(1500,w.timer.start)
        if mode == 'stop' and live and not stopped and w.stop_btn.isEnabled():
            stopped = True
            w.stop_btn.click()
        if mode == 'partial' and state == 'interrupted_recovered' and w.state['integrity_status'] == 'partial':
            finish()
        elif mode not in ('close','kill') and state in ('completed','cancelled') and w.report and w.backlog == 0:
            w.report_btn.click()
            finish()

    timer = QtCore.QTimer()
    timer.timeout.connect(tick)
    timer.start(50)
    QtCore.QTimer.singleShot(150000,app.quit)
    app.exec()
    w.client.closed.set()
    (case/'gui.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main(*sys.argv[1:]))
