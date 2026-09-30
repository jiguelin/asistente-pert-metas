import json,unittest
from types import SimpleNamespace
from unittest.mock import patch
import pert_assistant as a
from intake import QUESTIONS

class ResumeAnswersTests(unittest.TestCase):
 def run_extract(self,messages,payload):
  resp=SimpleNamespace(output_text=json.dumps(payload),usage=None)
  with patch.object(a,'_create',return_value=resp):return a.extract_intake(None,'test',messages,'2026-09-30',{'input_tokens':0,'output_tokens':0})
 def payload(self):return {'hechos':[],'meta_verificable':False,'ambiguedad_esencial':None,'meta_cambiada':False,'cambio_meta_cita':None}
 def test_resume_does_not_erase_obstacles_answered_in_our_question(self):
  s=self.run_extract([{'role':'assistant','content':QUESTIONS['obstaculos']},{'role':'user','content':'Constancia, distracciones y cansancio.'}],self.payload())
  self.assertEqual(s['facts']['obstaculos'],'Constancia, distracciones y cansancio.')
 def test_unknown_skill_is_not_treated_as_a_developed_skill(self):
  s=self.run_extract([{'role':'assistant','content':QUESTIONS['habilidades']},{'role':'user','content':'No sé.'}],self.payload())
  self.assertNotIn('habilidades',s['facts'])
