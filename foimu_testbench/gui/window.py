import json
from pathlib import Path
import queue
import time
from PySide6 import QtCore, QtWidgets as W
import numpy as np
import pyqtgraph as pg
from ..evidence import loads
from ..presentation import series, filtered, UNITS
from ..scenarios import Scenario, import_v1
from .client import Client

STATES = dict(draft='Rascunho', validated='Validada', prepared='Preparada', armed='Armada',
              running='Em execução', stopping='Parando', finalizing='Finalizando', completed='Concluída',
              failed='Falha', aborted='Abortada', cancelled='Cancelada', passed='Aprovada',
              inconclusive='Inconclusiva', not_evaluated='Não avaliada', unknown='Desconhecida',
              partial='Parcial', corrupt='Corrompida', complete='Completa', interrupted_recovered='Interrompida, reaberta')
LABELS = dict(frames_accepted='Frames aceitos', checksum_errors='Candidatos com checksum inválido',
              framing_errors='Episódios de framing', resync_events='Ressincronizações',
              packets_lost='Lacunas candidatas de counter', jitter_max_s='Jitter máximo (s)',
              byte_silence_episodes='Silêncio de bytes', valid_frame_silence_episodes='Silêncio de frame válido')
DOMAIN = dict(control='Controle', observed='Observado', diagnostic='Diagnóstico', truth='Truth', validation='Validação')
SEVERITY = dict(info='Informação', warning='Aviso', error='Erro', critical='Crítica')
EPISTEMIC = dict(observed_fact='Fato observado', simulator_truth='Truth do simulador', inference='Inferência', hypothesis='Hipótese', unknown='Desconhecido')
KINDS = dict(checksum_candidate_rejected='Checksum inválido', discard='Descarte', resync='Ressincronização',
             counter_discontinuity='Descontinuidade de counter', byte_silence='Silêncio de bytes',
             valid_frame_silence='Silêncio de frame válido', stop_requested='Parada solicitada',
             stop_ack='ACK de parada', execution_transition='Transição de execução')
FAULTS = dict(drop_every='Perda', checksum_every='Checksum', byte_every='Byte', header_every='Header',
              truncate_every='Truncamento', jitter_s='Jitter (s)')


def box():
    w = W.QPlainTextEdit()
    w.setReadOnly(True)
    return w


def button(text, callback):
    w = W.QPushButton(text)
    w.clicked.connect(callback)
    return w


class Window(W.QMainWindow):
    def __init__(self, port=8877, client=None):
        super().__init__()
        self.client = client or Client(port)
        self.pending = self.expected_id = None
        self.state = {}
        self.connected = False
        self.rows, self.events, self.visible = [], [], []
        self.rate = 100
        self.report = None
        self.backlog = None
        self.perf = dict(max_age_ms=0, max_draw_ms=0)
        self.wall, self.cpu = time.monotonic(), time.process_time()
        self.setWindowTitle('FO-IMU Testbench | Bancada de comunicação')
        self.resize(1350, 900)
        root = W.QWidget()
        self.setCentralWidget(root)
        layout = W.QVBoxLayout(root)
        self.notice = W.QLabel('Conectando ao serviço local')
        layout.addWidget(self.notice)
        split = W.QSplitter()
        layout.addWidget(split, 4)
        self.config = W.QWidget()
        split.addWidget(self.config)
        form = W.QFormLayout(self.config)
        form.addRow(W.QLabel('Configuração do ensaio'))
        form.addRow('Perfil', W.QLabel('gateway53-fletcher16-le-v1'))
        form.addRow('Fidelidade / sinal', W.QLabel('L1 / synthetic_v1'))
        self.rate_edit, self.number, self.seed, self.fragment = [W.QLineEdit() for _ in range(4)]
        self.stop_kind = W.QComboBox()
        self.stop_kind.addItems(['Oportunidades', 'Duração virtual (s)'])
        self.out = W.QLineEdit(str(Path('logs') / f'ensaio_{time.time_ns()}'))
        for name, widget in [('Taxa virtual (Hz)', self.rate_edit), ('Término', self.stop_kind),
                             ('Valor', self.number), ('Seed', self.seed), ('Fragmentos (B)', self.fragment),
                             ('Saída nova', self.out)]:
            form.addRow(name, widget)
        form.addRow(W.QLabel('Falhas periódicas por oportunidade'))
        self.faults = {}
        for kind, name in FAULTS.items():
            enabled, value = W.QCheckBox(name), W.QLineEdit()
            form.addRow(enabled, value)
            self.faults[kind] = enabled, value
        form.addRow(button('Carregar cenário JSON', self.pick_scenario))
        self.recipe = W.QPlainTextEdit()
        form.addRow('Scenario v2', self.recipe)
        form.addRow(button('Aplicar JSON aos campos', self.apply_json))
        self.tabs = W.QTabWidget()
        split.addWidget(self.tabs)
        panel = W.QWidget()
        graphs = W.QVBoxLayout(panel)
        graphs.addWidget(W.QLabel('Recepção no relógio virtual experiment | Janela de até 60 s'))
        self.graphs = []
        pg.setConfigOption('foreground', '#293849')
        for i in range(3):
            combo = W.QComboBox()
            for k in UNITS:
                label = k.replace('temp_', 'Temperatura, slot inferido ').replace('_', ' ')
                combo.addItem(label if k.startswith('temp_') else label.upper(), k)
            combo.setCurrentIndex(i)
            plot = pg.PlotWidget(background='#fafafa')
            plot.setMenuEnabled(False)
            plot.setLabel('bottom', 'Tempo de recepção virtual', units='s')
            plot.showGrid(x=True, y=True, alpha=.15)
            curve = plot.plot(pen='#006ba1', connect='finite')
            self.graphs.append((combo, plot, curve))
            graphs.addWidget(combo)
            graphs.addWidget(plot)
            combo.currentIndexChanged.connect(self.plot)
        self.tabs.addTab(panel, 'Sinais observados')
        self.report_view, self.truth_view = box(), box()
        self.tabs.addTab(self.report_view, 'Relatório original')
        self.tabs.addTab(self.truth_view, 'Truth do simulador')
        self.tabs.setTabVisible(2, False)
        side = W.QWidget()
        split.addWidget(side)
        info = W.QVBoxLayout(side)
        self.status = W.QLabel()
        self.status.setWordWrap(True)
        info.addWidget(self.status)
        self.metrics, self.health = box(), box()
        info.addWidget(self.metrics)
        info.addWidget(self.health)
        self.performance = W.QLabel()
        self.performance.setWordWrap(True)
        info.addWidget(self.performance)
        truth = W.QCheckBox('Exibir truth do simulador')
        truth.toggled.connect(lambda on: self.tabs.setTabVisible(2,on))
        info.addWidget(truth)
        split.setSizes([300,680,360])
        filters = W.QHBoxLayout()
        layout.addLayout(filters)
        filters.addWidget(W.QLabel('Eventos recentes'))
        self.domain, self.severity = W.QComboBox(), W.QComboBox()
        self.component = W.QLineEdit()
        self.component.setPlaceholderText('Filtrar componente')
        for combo, names, title in [(self.domain, DOMAIN, 'Todos os domínios'), (self.severity, SEVERITY, 'Todas as severidades')]:
            combo.addItem(title, '')
            for k,v in names.items(): combo.addItem(v,k)
            combo.currentIndexChanged.connect(self.timeline)
            filters.addWidget(combo)
        self.component.textChanged.connect(self.timeline)
        filters.addWidget(self.component)
        self.table = W.QTableWidget(0,8)
        self.table.setHorizontalHeaderLabels(['Tempo e clock','Domínio','Componente','Faceta','Severidade','Conhecimento','Evento','Bytes [início, fim)'])
        self.table.setSelectionBehavior(W.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(W.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.detail)
        layout.addWidget(self.table,1)
        self.details = box()
        self.details.setMaximumHeight(75)
        layout.addWidget(self.details)
        controls = W.QHBoxLayout()
        layout.addLayout(controls)
        self.start_btn = button('Iniciar', self.start_run)
        self.stop_btn = button('Parar', self.stop_run)
        self.open_btn = button('Abrir Run', self.pick_run)
        self.report_btn = button('Abrir relatório', lambda: self.tabs.setCurrentIndex(1))
        for w in (self.start_btn,self.stop_btn,self.open_btn,self.report_btn): controls.addWidget(w)
        self.load(import_v1({'packets':6000}))
        self.buttons()
        self.plot()
        self.timer = QtCore.QTimer(self)
        self.timer.setTimerType(QtCore.Qt.TimerType.PreciseTimer)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.client.start()

    def load(self, s):
        self.recipe.setPlainText(json.dumps(s.to_dict(), ensure_ascii=False, indent=2))
        self.rate_edit.setText(str(s.rate.value))
        self.stop_kind.setCurrentIndex(int(s.stop_condition.kind == 'duration'))
        self.number.setText(str(s.stop_condition.count if s.stop_condition.count is not None else s.stop_condition.duration.value))
        self.seed.setText(str(s.seed))
        self.fragment.setText(', '.join(map(str,s.fragmentation.chunk_sizes)))
        rules = {r.kind:r for r in s.fault_rules}
        for kind,(enabled,value) in self.faults.items():
            r = rules.get(kind)
            enabled.setChecked(bool(r and r.enabled))
            value.setText(str((r.jitter.value if kind == 'jitter_s' else r.every) if r else 0))

    def scenario(self):
        p = Scenario.from_json(self.recipe.toPlainText()).to_dict()
        p['rate']['value'] = float(self.rate_edit.text())
        p['seed'] = int(self.seed.text())
        p['fragmentation']['chunk_sizes'] = [int(x) for x in self.fragment.text().split(',')]
        stop = p['stop_condition']
        if self.stop_kind.currentIndex():
            stop.update(kind='duration', count=None, duration=dict(schema_version=2,unit='s',value=float(self.number.text())))
        else:
            stop.update(kind='opportunities', count=int(self.number.text()), duration=None)
        by_kind = {r['kind']:r for r in p['fault_rules']}
        for default in import_v1({}).to_dict()['fault_rules']:
            kind = default['kind']
            r = by_kind.setdefault(kind,default)
            check, edit = self.faults[kind]
            r['enabled'] = check.isChecked()
            if kind == 'jitter_s': r['jitter']['value'] = float(edit.text())
            else: r['every'] = int(edit.text())
        p['fault_rules'] = list(by_kind.values())
        return Scenario.from_dict(p)

    def pick_scenario(self):
        path, _ = W.QFileDialog.getOpenFileName(self,'Carregar cenário','','JSON (*.json)')
        if path:
            try: self.load(Scenario.from_json(Path(path).read_bytes()))
            except (OSError,ValueError) as e: self.notice.setText(str(e))

    def apply_json(self):
        try: self.load(Scenario.from_json(self.recipe.toPlainText()))
        except ValueError as e: self.notice.setText(str(e))

    def issue(self, kind, payload):
        if self.pending: return
        self.pending = self.client.submit(kind,payload)
        self.notice.setText('Aguardando ACK do comando ' + self.pending)
        self.buttons()

    def start_run(self):
        try: self.issue('start_run',dict(scenario=self.scenario().to_dict(),out=self.out.text()))
        except ValueError as e: self.notice.setText(str(e))

    def stop_run(self):
        self.issue('stop_run',dict(run_id=self.state.get('run_id'),reason='Parada solicitada pela GUI'))

    def pick_run(self):
        path = W.QFileDialog.getExistingDirectory(self, 'Abrir Run v2')
        if path: self.issue('open_run',dict(path=path))

    def buttons(self):
        ready = self.connected and not self.pending
        self.start_btn.setEnabled(bool(ready and self.state.get('can_start')))
        self.open_btn.setEnabled(self.start_btn.isEnabled())
        self.stop_btn.setEnabled(bool(ready and self.state.get('can_stop')))
        self.report_btn.setEnabled(bool(self.report and self.connected))
        self.config.setEnabled(not self.connected or bool(self.state.get('can_start')))

    def refresh(self):
        try: reply = loads(self.client.replies.get_nowait())
        except queue.Empty: reply = None
        if reply:
            self.pending = None
            if reply['successful'] and reply.get('accepted'):
                self.notice.setText('ACK aceito: ' + reply['command_id'])
                if reply.get('run_id'): self.expected_id = reply['run_id']
            else: self.notice.setText(reply.get('detail','Comando recusado') + ' | ' + reply['command_id'])
        raw = self.client.latest.take()
        if raw is None:
            self.buttons()
            return
        data = loads(raw)
        self.connected = data['connected']
        if not self.connected:
            self.expected_id = None
            self.state = {}
            self.status.setText('Serviço desconectado\nExecução: desconhecida\nAvaliação: desconhecida\nIntegridade: desconhecida')
            self.notice.setText('Reconectando. Para recuperação, inicie o serviço e use Abrir Run.')
        else:
            parts = {m['message_type']:m['payload'] for m in data['messages']}
            state = parts['run_state']
            if self.expected_id and self.expected_id != state['run_id']: return
            self.expected_id = None
            self.state = state
            self.status.setText('\n'.join([f"Run: {state['run_id'] or 'nenhuma'}",
                'Execução: ' + STATES[state['execution_status']], 'Avaliação: ' + STATES[state['evaluation_status']],
                'Integridade: ' + STATES[state['integrity_status']], state['reason'] or '', *state['issues']]))
            self.render(parts)
            self.perf['max_age_ms'] = max(self.perf['max_age_ms'], (time.monotonic_ns()-data['produced_monotonic_ns'])/1e6)
            self.perf.update(self.client.stats(), frames=len(self.rows), events=len(self.events),
                cpu_percent=100*(time.process_time()-self.cpu)/(time.monotonic()-self.wall))
            self.performance.setText(f"Apresentação: {self.perf['rate_hz'] or 0:.2f} Hz\nSnapshots substituídos: {self.perf['replaced']}\nSequências omitidas: {self.perf['skipped']}\nIdade máxima: {self.perf['max_age_ms']:.0f} ms\nBuffer: {len(self.rows)}/6000 frames\nCPU média da GUI: {self.perf['cpu_percent']:.1f}%")
        self.buttons()

    def render(self, parts):
        if 'error' in parts: self.notice.setText(parts['error']['detail'])
        signals = parts.get('signal_snapshot',{})
        rows = signals.get('rows',[])
        if rows != self.rows:
            self.rows = rows
            self.rate = signals.get('rate_hz',100)
            self.plot()
        events = parts.get('event_snapshot',{}).get('events',[])
        if events != self.events:
            self.events = events
            self.timeline()
        metrics = parts.get('metrics_snapshot',{})
        self.metrics.setPlainText(metrics.get('origin','Aguardando registros')+'\n'+'\n'.join(
            f"{label}: {metrics.get('values',{}).get(key,'?')}" for key,label in LABELS.items()))
        health = parts.get('pipeline_health',{})
        self.backlog = health.get('presentation_backlog_bytes')
        lines = []
        for key in ('rx','writer'):
            q = health.get(key,{})
            lines.append(f"{key.upper()}: {q.get('bytes','?')} B, pico {q.get('peak_bytes','?')} B, pendentes {q.get('pending','?')}")
        lines.extend([f"Workers ativos: {health.get('workers',health.get('workers_alive','?'))}",
                      f"Registros pendentes para exibição: {self.backlog} B"])
        self.health.setPlainText('\n'.join(lines))
        terminal = parts.get('run_finished',{})
        report = terminal.get('report')
        if report != self.report:
            self.report = report
            self.report_view.setPlainText(report or 'Relatório indisponível')
        self.truth_view.setPlainText(json.dumps(terminal['truth'],ensure_ascii=False,indent=2) if terminal.get('truth') else 'Resumo de truth indisponível')

    def plot(self):
        started = time.monotonic()
        for combo, plot, curve in self.graphs:
            k = combo.currentData()
            x,y = series(self.rows,k,self.rate)
            curve.setData(np.asarray(x), np.asarray(y), connect='finite')
            plot.setLabel('left',combo.currentText(),units=UNITS[k])
        self.perf['max_draw_ms'] = max(self.perf['max_draw_ms'],1000*(time.monotonic()-started))

    def timeline(self):
        self.visible = filtered(self.events,self.domain.currentData(),self.component.text(),self.severity.currentData())
        self.table.setRowCount(len(self.visible))
        for i,e in enumerate(self.visible):
            t,span = e.get('time') or {},e.get('byte_span')
            values = [f"{t.get('value','?')} ns / {t.get('clock_id','?')}",DOMAIN[e['domain']],e['component_path'],
                      e['facet'] or '',SEVERITY[e['severity']],EPISTEMIC[e['epistemic_status']],KINDS.get(e['kind'],e['kind']),
                      f"[{span['start']}, {span['end']})" if span else 'indisponível']
            for j,v in enumerate(values): self.table.setItem(i,j,W.QTableWidgetItem(v))
        self.detail()

    def detail(self):
        i = self.table.currentRow()
        self.details.setPlainText(json.dumps(self.visible[i],ensure_ascii=False,indent=2) if 0 <= i < len(self.visible) else '')

    def closeEvent(self,event):
        self.timer.stop()
        self.client.closed.set()
        event.accept()
