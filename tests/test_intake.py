import unittest
from intake import calculations,normalize,stage,cash_schedule,business_windows

class IntakeTests(unittest.TestCase):
    def test_paid_october_is_not_charged_twice(self):
        f={'inicio':'2026-10-01','fin':'2026-12-31','tipo':'ahorro','saldo':'1500','ingreso':'2200','gasto':'1200','reserva':'1200','objetivo':'4000','gastos_inicio_pagados':'true','cobro_fin_mes':'true'}
        s=calculations(f)
        self.assertIn('libre 4500',s)
        self.assertIn('brecha 0',s)
        self.assertIn('2026-10-04 domingo',s)
        self.assertEqual([(r['saldo'],r['reserva'],r['libre']) for r in cash_schedule(f)],
                         [(1500,0,1500),(3700,1200,2500),(4700,1200,3500),(5700,1200,4500)])

    def test_no_calendar_or_montage_without_a_real_start(self):
        snapshot={'facts':{'meta':'Caminar 5 km','fin':'2026-11-29'},'meta_verificable':True,'ambiguedad_esencial':None}
        self.assertEqual(stage(snapshot),'inicio')
        snapshot['facts']['inicio']='2026-02-30'
        self.assertEqual(stage(snapshot),'inicio')

    def test_unattributed_facts_are_discarded(self):
        p={'ambiguedad_esencial':None,'meta_verificable':True,'hechos':[{'campo':'inicio','valor':'2026-10-01','usuario':0,'cita':'empiezo el 1 de octubre'}]}
        self.assertNotIn('inicio',normalize(p,['Quiero caminar 5 km'])['facts'])

    def test_literal_quote_survives_wrong_message_index(self):
        p={'ambiguedad_esencial':None,'meta_verificable':True,'hechos':[{'campo':'meta','valor':'Caminar 5 km','usuario':1,'cita':'caminar 5 km'}]}
        self.assertEqual(normalize(p,['Quiero caminar 5 km'])['facts']['meta'],'Caminar 5 km')

    def test_business_reserve_does_not_change_profit(self):
        f={'tipo':'empresa','unidades':'10','precio':'100','costo':'40','empaque':'5','publicidad':'40','reposicion_caja':'40','reposicion_empaque':'5','reposicion_envio':'10'}
        self.assertIn('reposición 455',calculations(f))

    def test_courier_deadline_keeps_time_for_replacement(self):
        f={'tipo':'empresa','fin':'2026-11-15','entrega_habiles':'2','reposicion_habiles':'1','entrega_lun_vie':'true','recogida_sabados':'true'}
        self.assertEqual(business_windows(f),{'cobro_y_envio_normal_maximo':'2026-11-07','entrega_normal_y_pedido_reposicion_maximo':'2026-11-10','recepcion_y_reenvio_reposicion_maximo':'2026-11-11','entrega_reposicion_maximo':'2026-11-13'})
        f['recogida_sabados']='false'
        self.assertEqual(business_windows(f)['cobro_y_envio_normal_maximo'],'2026-11-06')

    def test_known_dimensions_survive_omission_but_approval_does_not(self):
        previous={'meta_nota':'[15,15]','mini_aprobadas':'true'}
        payload={'ambiguedad_esencial':None,'meta_verificable':True,'hechos':[]}
        facts=normalize(payload,['Sí'],previous)['facts']
        self.assertEqual(facts['meta_nota'],'[15,15]')
        self.assertNotIn('mini_aprobadas',facts)

if __name__=='__main__':unittest.main()
