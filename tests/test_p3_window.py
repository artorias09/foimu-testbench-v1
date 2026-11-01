import importlib.util
import os
import queue
import sys
import threading
import unittest
from foimu_testbench.gui.client import Latest
from foimu_testbench.evidence import dumps

HAS_GUI = all(importlib.util.find_spec(x) for x in ('PySide6','pyqtgraph','numpy'))


@unittest.skipUnless(HAS_GUI, 'Requer dependências opcionais da GUI')
class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != 'win32' and not os.environ.get('DISPLAY'):
            os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        from foimu_testbench.gui.window import Window
        from foimu_testbench.gui.client import Client
        from unittest.mock import patch
        self.client=Client(1)
        with patch.object(self.client,'start'):
            self.w=Window(client=self.client)
        self.w.timer.stop()

    def tearDown(self):
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()

    def test_observed_diagnostic_and_optional_truth(self):
        self.w.render({'metrics_snapshot':{'values':{'packets_lost':2,'frames_accepted':8}},
                       'run_finished':{'report':'# Relatório original','truth':{'dropped':3}}})
        shown=self.w.metrics.toPlainText()
        self.assertIn('Frames aceitos: 8',shown.split('Diagnóstico do fluxo')[0])
        self.assertIn('Lacunas candidatas de counter: 2',shown.split('Diagnóstico do fluxo')[1])
        self.assertFalse(self.w.tabs.isTabVisible(2))
        self.assertNotIn('dropped',shown)
        self.assertEqual(self.w.report_view.toPlainText(),'# Relatório original')

    def test_disconnect_disables_controls_and_never_sends_stop(self):
        self.client.latest.put(dumps({'connected':False,'detail':'Teste'}))
        self.w.refresh()
        self.assertIn('Execução: desconhecida',self.w.status.text())
        self.assertFalse(self.w.stop_btn.isEnabled())
        self.w.close()
        self.assertTrue(self.client.commands.empty())

    def test_select_event_and_filter_component(self):
        self.w.events=[dict(kind='discard',event_id='d',domain='observed',component_path='FO-IMU/Host',
            facet='Protocolo',severity='warning',epistemic_status='observed_fact',byte_span={'start':0,'end':2})]
        self.w.timeline()
        self.w.table.selectRow(0)
        self.assertIn('"event_id": "d"',self.w.details.toPlainText())
        self.w.component.setText('ACC')
        self.assertEqual(self.w.table.rowCount(),0)
        self.assertEqual(self.w.details.toPlainText(),'')

    def test_configure_duration_and_enable_checksum(self):
        self.w.stop_kind.setCurrentIndex(1)
        self.w.number.setText('1.5')
        toggle, field=self.w.faults['checksum_every']
        toggle.setChecked(True)
        field.setText('10')
        recipe=self.w.scenario()
        self.assertEqual(recipe.stop_condition.duration.value,1.5)
        rule=next(r for r in recipe.fault_rules if r.kind=='checksum_every')
        self.assertTrue(rule.enabled)
        self.assertEqual(rule.every,10)
