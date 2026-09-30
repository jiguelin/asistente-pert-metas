import unittest
from unittest.mock import patch
from copy import deepcopy
from datetime import date,timedelta
import visual_assistant as va
from visual_plan import audit_visual,periods,final_text
from pdf_export import export_pdf
from progress import export_progress,import_progress

def sample():
    p={'meta':'Elaborar una tabla dinámica sin ayuda al 31 de octubre de 2026','inicio':'2026-10-01','fin':'2026-10-31','situacion':'Sé fórmulas básicas.','principal':'Distracciones','estrategia':'Empezar protegiendo la práctica del celular, con apoyo de una amiga.','secuencia':'Primero datos preparados; después reporte autónomo. La concentración se trabaja en paralelo.','conexiones':[],'notas':[]}
    for id,t,title,d in [('M1','M','Datos preparados','2026-10-10'),('M2','M','Prueba autónoma superada','2026-10-25'),('T1','T','Practicar con datos','2026-10-01'),('O1','O','Distracciones','2026-10-01'),('H1','H','Aprender tablas dinámicas','2026-10-01'),('A1','A','Amiga y tutorial','2026-10-01'),('MP','MP','Reporte elaborado sin ayuda','2026-10-31')]:
        p['notas'].append({'id':id,'tipo':t,'texto':title,'detalle':title,'fecha':d,'evidencia':'Totales coinciden con la referencia.' if t in ('M','MP') else '', 'para':['M1','M2'] if t=='T' else []})
    p['conexiones']=[{'de':'M1','a':'M2','tipo':'antes'},{'de':'T1','a':'M1','tipo':'contribuye'}]
    return p

class VisualTests(unittest.TestCase):
    def test_period_coverage_and_three_columns(self):
        for days in [1,21,31,42,43,182,244,365,730]:
            p=sample();p['fin']=(date(2026,10,1)+timedelta(days=days-1)).isoformat()
            for n in p['notas']:n['fecha']=p['inicio'] if n['tipo']!='MP' else p['fin']
            a=audit_visual(p); ps=a['plan']['periodos']
            self.assertEqual(ps[0]['inicio'],p['inicio']);self.assertEqual(ps[-1]['fin'],p['fin'])
            for x,y in zip(ps,ps[1:]):self.assertEqual(date.fromisoformat(x['fin'])+timedelta(days=1),date.fromisoformat(y['inicio']))
            self.assertTrue(all(1<=len(g)<=3 for g in a['hojas']))
            self.assertEqual(sum(map(len,a['hojas'])),len(ps))
    def test_no_tasks_allowed(self):
        p=sample();p['notas']=[n for n in p['notas'] if n['tipo']!='T'];p['conexiones']=[e for e in p['conexiones'] if e['de']!='T1']
        a=audit_visual(p);self.assertNotIn('sesiones',a['plan']);self.assertIn('No hace falta añadir tareas',final_text(a))
    def test_invalid_precedence_and_cycle(self):
        p=sample();p['conexiones']=[{'de':'M2','a':'M1','tipo':'antes'}]
        with self.assertRaises(ValueError):audit_visual(p)
        p=sample();p['notas'][1]['fecha']=p['notas'][0]['fecha'];p['conexiones']+=[{'de':'M2','a':'M1','tipo':'antes'}]
        with self.assertRaises(ValueError):audit_visual(p)
    def test_shared_task_not_duplicated_and_main_outside(self):
        a=audit_visual(sample());self.assertEqual(sum(n['tipo']=='T' for n in a['plan']['notas']),1)
        self.assertEqual(next(n['columna'] for n in a['plan']['notas'] if n['tipo']=='MP'),'zona final')
    def test_import_rechecks_and_pdf_contains_legend(self):
        from pypdf import PdfReader
        from io import BytesIO
        a=audit_visual(sample());b=import_progress(export_progress([],a))['final']
        text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(export_pdf(b))).pages)
        for n in a['plan']['notas']:self.assertIn(n['texto'],text)
        self.assertIn('Cada semana',text);self.assertNotIn('minutos de',text)
    def test_acceptance_requires_no_api_or_second_approval(self):
        p=sample();m=[{'role':'assistant','content':'¿Te sirve esta ruta o quieres ajustar algo?'},{'role':'user','content':'Sí, acepto.'}]
        with patch.object(va,'call',side_effect=AssertionError('No API needed')):
            reply,done,u=va.respond(None,'test',m,'2026-09-30',{'_visual_proposal':p})
            self.assertTrue(done)
            a,missing,use=va.build_final(None,'test',m,'2026-09-30',u['snapshot'])
            self.assertEqual(use['output_tokens'],0);self.assertFalse(missing)
    def test_intake_ignores_hours_and_materials(self):
        f={k:'dato' for k in va.KEYS};f.update(inicio='2026-10-01',fin='2026-10-31')
        self.assertEqual(va.next_stage({'facts':f,'meta_verificable':True}),'propuesta')
        f.pop('principal');self.assertEqual(va.next_stage({'facts':f,'meta_verificable':True}),'principal')
    def test_multiple_facts_preserve_baseline_and_supports(self):
        user='Peso 66.5 kg. Energía mediana. Me apoya mi hermana y un courier.'
        payload={'ambiguedad_esencial':None,'meta_verificable':False,'meta_cambiada':False,'cambio_meta_cita':None,'hechos':[]}
        for key,value,quote in [('situacion','66.5 kg','66.5 kg'),('situacion','Energía mediana','Energía mediana'),('apoyos','hermana','mi hermana'),('apoyos','courier','un courier')]:
            payload['hechos'].append({'campo':key,'valor':value,'usuario':0,'cita':quote})
        f=va.normalize_visual(payload,[user])['facts']
        self.assertIn('66.5',f['situacion']);self.assertIn('Energía',f['situacion'])
        self.assertIn('hermana',f['apoyos']);self.assertIn('courier',f['apoyos'])

    def test_notebook_label_survives_bad_model_quote(self):
        user='Ahora sé fórmulas básicas. No tengo obstáculos. Habilidad a aprender: tablas dinámicas.'
        payload={'ambiguedad_esencial':None,'meta_verificable':False,'meta_cambiada':False,'cambio_meta_cita':None,'hechos':[{'campo':'habilidades','valor':'tablas dinámicas','usuario':0,'cita':'Ahora sé fórmulas básicas. Habilidad a aprender: tablas dinámicas'}]}
        self.assertEqual(va.normalize_visual(payload,[user])['facts']['habilidades'],'tablas dinámicas')

    def test_case_and_punctuation_do_not_erase_evidence(self):
        user='Necesito aprender disciplina, concentración y planificación.'
        payload={'ambiguedad_esencial':None,'meta_verificable':False,'meta_cambiada':False,'cambio_meta_cita':None,'hechos':[{'campo':'habilidades','valor':'Disciplina, concentración y planificación','usuario':0,'cita':'necesito aprender disciplina concentración y planificación'}]}
        self.assertIn('concentración',va.normalize_visual(payload,[user])['facts']['habilidades'])
        payload['hechos']=[]
        self.assertIn('disciplina',va.normalize_visual(payload,[user])['facts']['habilidades'])

    def test_repair_identifies_the_exact_invalid_edge(self):
        p=sample();p['conexiones']=[{'de':'M2','a':'T1','tipo':'antes'}]
        with self.assertRaisesRegex(ValueError,'M2.*2026-10-25.*T1.*2026-10-01'):
            audit_visual(p)

    def test_date_and_none_sentence_punctuation(self):
        user='Empiezo el 1 de octubre de 2026. No tengo obstáculos.'
        payload={'ambiguedad_esencial':None,'meta_verificable':False,'meta_cambiada':False,'cambio_meta_cita':None,'hechos':[{'campo':'inicio','valor':'2026-10-01.','usuario':0,'cita':'Empiezo el 1 de octubre de 2026'},{'campo':'obstaculos','valor':'Ninguno.','usuario':0,'cita':'No tengo obstáculos'}]}
        f=va.normalize_visual(payload,[user])['facts']
        self.assertEqual(f['inicio'],'2026-10-01');self.assertEqual(f['principal'],'Ninguno identificado')

    def test_prompt_bounds_and_strategy(self):
        self.assertLess(len(va.instructions()),8000)
        self.assertIn('obstáculo principal',va.instructions());self.assertIn('No calcules horas',va.instructions())

if __name__=='__main__':unittest.main()
