import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import pert_assistant as a

class StructuredPipelineTests(unittest.TestCase):
 def facts(self):
  f={k:'declarado' for k in ['situacion','obstaculos','principal','habilidades','apoyos','disponibilidad']}
  f.update(meta='Pesar 70 kg',inicio='2026-10-01',fin='2027-03-31',minutos_semana='[75,75,75,75,75,75,75]',mini_aprobadas='true',tipo='otro')
  return {'facts':f,'meta_verificable':True,'ambiguedad_esencial':None}
 def task(self,ident,minutes):
  return {'id':ident,'titulo':'Rutina propuesta','detalle':'Seguir la orientación del coach y registrar el avance.','inicio':'2026-10-01','fin':'2027-03-31','dias':list(range(7)),'minutos':minutes,'fechas':[],'excluir':[],'excepciones':[],'habilita':['M1','MP'],'requisitos':[],'orden_sesion':[],'pasos':[{'accion':'Preparar, realizar y registrar','minutos':minutes}]}
 def response(self,data):return SimpleNamespace(output_text=json.dumps(data),usage=None)
 def test_exact_calendar_is_checked_before_semantic_review(self):
  data={'tareas':[self.task('T1',45),self.task('T2',30)]}
  with patch.object(a,'extract_intake',return_value=self.facts()),patch.object(a,'_create',return_value=self.response(data)) as create,patch.object(a,'review',return_value={'ok':True,'problems':[]}) as review:
   reply,done,_=a.respond(None,'test',[{'role':'user','content':'Todos los días.'}],'2026-09-30')
  self.assertFalse(done);self.assertIn('364 sesiones',reply);self.assertIn('13650 min',reply)
  self.assertEqual(reply.count('?'),1);self.assertEqual(create.call_args.kwargs['text']['format']['name'],'pert_tasks')
  self.assertIn('validó cada sesión',review.call_args.args[4])
 def test_overloaded_proposal_never_reaches_reviewer_or_student(self):
  data={'tareas':[self.task('T1',45),self.task('T2',45)]}
  with patch.object(a,'extract_intake',return_value=self.facts()),patch.object(a,'_create',return_value=self.response(data)) as create,patch.object(a,'review') as review:
   with self.assertRaises(a.AssistantError):a.respond(None,'test',[{'role':'user','content':'Todos los días.'}],'2026-09-30')
  self.assertEqual(create.call_count,3);review.assert_not_called()
  self.assertIn('Carga diaria',create.call_args.kwargs['instructions'])
