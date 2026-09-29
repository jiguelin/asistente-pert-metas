import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pert_assistant import build_final
from test_product import sample_plan

class FinalApiContractTests(unittest.TestCase):
    def test_json_mode_request_contains_json_in_input(self):
        facts={key:'dato conocido' for key in ['meta','situacion','obstaculos','principal','habilidades','apoyos','disponibilidad']}
        facts.update(inicio='2026-10-01',fin='2026-10-31',mini_aprobadas='true',tareas_aprobadas='true',papel='[90,60]',nota='[3.8,3.8]',meta_nota='[15,15]',papeles='3',pared='300')
        facts['principal']='Lluvia'
        snapshot={'facts':facts,'meta_verificable':True,'ambiguedad_esencial':None}
        usage=SimpleNamespace(input_tokens=100,output_tokens=100)
        responses=[SimpleNamespace(output_text=json.dumps(sample_plan()),usage=usage),SimpleNamespace(output_text='{"ok":true,"problems":[]}',usage=usage)]
        with patch('pert_assistant._create',side_effect=responses) as create:
            audit,missing,_=build_final(None,'test-model',[{'role':'user','content':'Sí, acepto.'}],'2026-09-29',ready_snapshot=snapshot)
        self.assertFalse(missing)
        self.assertIsNotNone(audit)
        kwargs=create.call_args_list[0].kwargs
        self.assertEqual(kwargs['text']['format']['type'],'json_object')
        self.assertIn('json',json.dumps(kwargs['input']).lower())

if __name__=='__main__':unittest.main()
