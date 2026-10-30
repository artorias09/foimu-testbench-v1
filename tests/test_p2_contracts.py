import unittest
from dataclasses import replace
from test_p1_contracts import run


class P2ContractTests(unittest.TestCase):
    def test_stop_reason_survives_finalization(self):
        r = replace(run(), execution_status='running')
        r = r.transition('stopping', 'Solicitado pelo operador')
        self.assertEqual(r.transition('finalizing').stop_reason, 'Solicitado pelo operador')
        self.assertEqual(r.transition('finalizing', 'Falha no dreno').stop_reason, 'Falha no dreno')

    def test_final_identity_cannot_silently_claim_no_change(self):
        r=run()
        with self.assertRaises(ValueError):replace(r,sources_changed=False)
        with self.assertRaises(ValueError):replace(r,final_code_identity=r.code_identity,sources_changed=True)
        self.assertFalse(replace(r,final_code_identity=r.code_identity,sources_changed=False).sources_changed)
