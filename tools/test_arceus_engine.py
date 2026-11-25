#!/usr/bin/env python3
"""Tests unitarios para el motor determinista de Arceus Finanzas."""

import datetime as dt
import json
import unittest
from pathlib import Path

from arceus_engine import (
    EXAMPLE_PROFILE_PATH,
    calcular_ventana_pago,
    planificar_quincena,
    renderizar_markdown,
)


class TestArceusEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.perfil = json.loads(EXAMPLE_PROFILE_PATH.read_text(encoding="utf-8"))

    def test_ventana_quincena_15_y_30(self) -> None:
        v1 = calcular_ventana_pago(dt.date(2026, 11, 15), [15, 30])
        self.assertEqual(v1["proximo_pago"], dt.date(2026, 11, 30))
        self.assertEqual(v1["subsiguiente_pago"], dt.date(2026, 12, 15))
        self.assertEqual(v1["codigo_periodo"], "2026-11-Q1")

        v2 = calcular_ventana_pago(dt.date(2026, 11, 30), [15, 30])
        self.assertEqual(v2["proximo_pago"], dt.date(2026, 12, 15))
        self.assertEqual(v2["subsiguiente_pago"], dt.date(2026, 12, 30))
        self.assertEqual(v2["codigo_periodo"], "2026-11-Q2")

    def test_suma_exacta_y_prorrateo_q1(self) -> None:
        # En Q1 (15 nov -> 30 nov):
        # - Vencen directo: transporte (16 nov, 300 efectivo), gimnasio (18 nov, 250 débito),
        #   ayuda_casa (28 nov, 500 efectivo).
        # - La Renta (2000, día 1 dic) vence en la SIGUIENTE ventana (30 nov -> 15 dic),
        #   por lo que el motor debe apartar el 50% (1000) hoy para evitar apretón en Q2.
        plan = planificar_quincena(
            perfil=self.perfil,
            ingreso=4850.0,
            fecha_pago=dt.date(2026, 11, 15),
        )
        r = plan["resumen_montos"]
        self.assertEqual(r["ingreso_quincena"], 4850.0)
        self.assertEqual(r["verificacion_suma_exacta"], 4850.0)
        self.assertEqual(r["diferencia_redondeo"], 0.0)
        self.assertEqual(r["apartados_prorrateo_proxima_quincena"], 1000.0)
        self.assertEqual(plan["cubetas_metodo_pago"]["efectivo"], 800.0)
        self.assertEqual(plan["cubetas_metodo_pago"]["debito"], 250.0)
        self.assertGreaterEqual(r["gastos_libres_salidas"], 800.0)
        self.assertGreater(r["ahorro_fuerte_total"], 1000.0)

    def test_suma_exacta_y_tc_q2(self) -> None:
        # En Q2 (30 nov -> 15 dic):
        # - Vence Renta (1 dic, 2000 transferencia -> toma 1000 de este ingreso y 1000 del apartado previo)
        # - Vence Internet (10 dic, 350 con TC -> genera apartado TC de 350 en débito)
        plan = planificar_quincena(
            perfil=self.perfil,
            ingreso=4200.0,
            fecha_pago=dt.date(2026, 11, 30),
        )
        r = plan["resumen_montos"]
        self.assertEqual(r["verificacion_suma_exacta"], 4200.0)
        self.assertEqual(plan["cubetas_metodo_pago"]["transferencia"], 1000.0)
        self.assertEqual(plan["cubetas_metodo_pago"]["tc"], 350.0)
        self.assertEqual(r["apartado_tc_en_debito"], 350.0)
        md = renderizar_markdown(plan)
        self.assertIn("Plan Quincenal Arceus", md)
        self.assertIn("Mi Primera TC", md)


if __name__ == "__main__":
    unittest.main()
