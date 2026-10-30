import unittest
from dataclasses import replace
from test_p1_contracts import run


class P2ContractTests(unittest.TestCase):
    def test_stop_reason_survives_finalization(self):
        r = replace(run(), execution_status='running')
        r = r.transition('stopping', 'Solicitado pelo operador')
        self.assertEqual(r.transition('finalizing').stop_reason, 'Solicitado pelo operador')
        self.assertEqual(r.transition('finalizing', 'Falha no dreno').stop_reason, 'Falha no dreno')
