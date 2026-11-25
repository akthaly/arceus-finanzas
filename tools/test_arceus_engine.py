#!/usr/bin/env python3
"""Tests unitarios para el motor determinista y asesor de compras de Arceus Finanzas."""

import datetime as dt
import json
import unittest

from arceus_engine import (
    EXAMPLE_PROFILE_PATH,
    calcular_ventana_pago,
    evaluar_compra,
    planificar_quincena,
    renderizar_evaluacion_compra_md,
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

    def test_suma_exacta_y_prorrateo_q1(self) -> None:
        plan = planificar_quincena(
            perfil=self.perfil,
            ingreso=4850.0,
            fecha_pago=dt.date(2026, 11, 15),
        )
        r = plan["resumen_montos"]
        self.assertEqual(r["verificacion_suma_exacta"], 4850.0)
        self.assertEqual(r["diferencia_redondeo"], 0.0)
        self.assertEqual(r["apartados_prorrateo_proxima_quincena"], 1000.0)

    def test_modo_compacto_ahorra_tokens(self) -> None:
        plan = planificar_quincena(
            perfil=self.perfil,
            ingreso=4200.0,
            fecha_pago=dt.date(2026, 11, 30),
        )
        md_full = renderizar_markdown(plan, compact=False)
        md_compact = renderizar_markdown(plan, compact=True)
        self.assertLess(len(md_compact), len(md_full))
        self.assertIn("Mejor fecha para comprar:", md_compact)

    def test_evaluar_compra_y_ventana_oro(self) -> None:
        # En el ejemplo el día de corte es 8 y día límite de pago es 28.
        # Si evaluamos el 5 de diciembre (3 días antes del corte), la ventana de oro es el 9 de diciembre.
        ev = evaluar_compra(
            perfil=self.perfil,
            monto_compra=1200.0,
            nombre_compra="Ropa Fin de Año",
            fecha_actual=dt.date(2026, 12, 5),
        )
        tc = ev["calendario_optimo_tc"]
        self.assertIsNotNone(tc)
        self.assertEqual(tc["ventana_oro_recomendada"]["fecha_compra"], "2026-12-09")
        self.assertGreater(
            tc["ventana_oro_recomendada"]["dias_financiamiento_gratis"],
            tc["si_compras_hoy"]["dias_financiamiento_gratis"],
        )
        md = renderizar_evaluacion_compra_md(ev)
        self.assertIn("Ventana de Oro", md)
        self.assertIn("Simulación en Cuotas SIN Intereses", md)


if __name__ == "__main__":
    unittest.main()
