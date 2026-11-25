#!/usr/bin/env python3
"""
Motor determinista de Arceus Finanzas (tools/arceus_engine.py).

Resuelve los dos problemas clásicos de usar un LLM puro para finanzas:
1. Fechas exactas: calcula ventanas reales del calendario entre días de pago,
   vencimientos de gastos fijos y fechas de corte/límite de tarjeta de crédito.
2. Matemáticas exactas al centavo: suma cubetas (efectivo, transferencia, débito,
   apartado de tarjeta de crédito), aplica prorrateo ("anti-apretón") para gastos
   fuertes, protege el piso de gastos libres/salidas y calcula el ahorro fuerte.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE_PATH = ROOT_DIR / "perfil" / "usuario.json"
EXAMPLE_PROFILE_PATH = ROOT_DIR / "perfil" / "usuario.example.json"
HISTORIAL_CSV_PATH = ROOT_DIR / "historial" / "quincenas.csv"
REPORTES_DIR = ROOT_DIR / "reportes"


def clamp_day(year: int, month: int, day: int) -> dt.date:
    """Convierte un día (1..31) en una fecha válida del mes (ajustando 28/29/30/31)."""
    last_day = calendar.monthrange(year, month)[1]
    return dt.date(year, month, min(max(1, day), last_day))


def next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def prev_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def calcular_ventana_pago(fecha_actual: dt.date, dias_pago: list[int]) -> dict[str, Any]:
    """
    Dado el día en que se recibe el pago (fecha_actual) y la lista de días de pago
    mensuales (ej. [15, 30]), devuelve:
    - fecha_inicio: fecha_actual
    - proximo_pago: fecha exacta del siguiente día de pago
    - fin_siguiente_ventana: fecha exacta del pago subsiguiente (para prorratear
      gastos grandes que vencen en la siguiente quincena)
    - codigo_periodo: ej. '2026-11-Q2'
    """
    dias_ordenados = sorted(set(dias_pago)) or [15, 30]

    # Generar fechas candidatas de pago en mes anterior, actual y siguientes 2 meses
    candidatos: list[dt.date] = []
    y, m = prev_month(fecha_actual.year, fecha_actual.month)
    for _ in range(4):
        for d in dias_ordenados:
            candidatos.append(clamp_day(y, m, d))
        y, m = next_month(y, m)
    candidatos = sorted(set(candidatos))

    # Si hoy está a 1-3 días antes de un día de pago oficial (ej. pagan viernes 13 en vez del 15),
    # saltamos ese día de pago inmediato para que la ventana cubra toda la quincena real.
    futuros = [c for c in candidatos if (c - fecha_actual).days > 4]
    proximo_pago = futuros[0]
    subsiguiente_pago = futuros[1]

    quincena_num = 1 if fecha_actual.day <= 20 else 2
    codigo_periodo = f"{fecha_actual.year:04d}-{fecha_actual.month:02d}-Q{quincena_num}"

    return {
        "fecha_inicio": fecha_actual,
        "proximo_pago": proximo_pago,
        "subsiguiente_pago": subsiguiente_pago,
        "dias_ventana": (proximo_pago - fecha_actual).days,
        "codigo_periodo": codigo_periodo,
    }


def proxima_ocurrencia_dia(desde: dt.date, dia_mes: int) -> dt.date:
    """Devuelve la primera fecha >= `desde` cuyo día del mes corresponde a `dia_mes`."""
    cand_actual = clamp_day(desde.year, desde.month, dia_mes)
    if cand_actual >= desde:
        return cand_actual
    ny, nm = next_month(desde.year, desde.month)
    return clamp_day(ny, nm, dia_mes)


def analizar_tarjeta_credito(
    tc: dict[str, Any],
    fecha_inicio: dt.date,
    proximo_pago: dt.date,
    cargos_tc_quincena: float,
    simbolo: str,
) -> dict[str, Any]:
    """
    Calcula fechas exactas de corte y límite de pago de la tarjeta de crédito,
    determina si toca liquidar el saldo al corte en esta quincena, calcula el uso
    del límite (regla del <30%) y genera consejos prácticos para principiantes.
    """
    dia_corte = int(tc.get("dia_corte", 10))
    dia_limite = int(tc.get("dia_limite_pago", 28))
    limite_credito = float(tc.get("limite_credito", 0.0))
    saldo_corte_pendiente = float(tc.get("saldo_al_corte_pendiente", 0.0))
    cuotas_fijas_mes = float(tc.get("cuotas_fijas_mes", 0.0))

    proximo_corte = proxima_ocurrencia_dia(fecha_inicio, dia_corte)
    proximo_limite = proxima_ocurrencia_dia(fecha_inicio, dia_limite)

    dias_para_corte = (proximo_corte - fecha_inicio).days
    dias_para_limite = (proximo_limite - fecha_inicio).days
    vence_en_esta_quincena = fecha_inicio <= proximo_limite < proximo_pago

    pago_saldo_anterior = saldo_corte_pendiente if vence_en_esta_quincena else 0.0
    apartado_nuevos_cargos = cargos_tc_quincena + (cuotas_fijas_mes / 2.0)
    apartado_total_tc = round(pago_saldo_anterior + apartado_nuevos_cargos, 2)

    uso_estimado = saldo_corte_pendiente + cargos_tc_quincena + cuotas_fijas_mes
    porcentaje_uso = round((uso_estimado / limite_credito) * 100.0, 1) if limite_credito > 0 else 0.0
    limite_saludable_30 = round(limite_credito * 0.30, 2)

    consejos: list[str] = []
    if dias_para_corte <= 4:
        consejos.append(
            f"Tu fecha de corte es muy pronto ({proximo_corte.isoformat()}, en {dias_para_corte} días). "
            "Lo que compres hoy con la TC entrará en el estado de cuenta que cierra ya. "
            "Si tienes una compra grande no urgente, espera un día después del corte para ganar ~45 días sin intereses."
        )
    else:
        consejos.append(
            f"Estás en buena ventana de financiamiento: tu próximo corte es el {proximo_corte.isoformat()} "
            f"(faltan {dias_para_corte} días)."
        )

    if vence_en_esta_quincena and saldo_corte_pendiente > 0:
        consejos.append(
            f"ATENCIÓN TOTALERO: Tu fecha límite de pago ({proximo_limite.isoformat()}) cae en esta quincena. "
            f"Paga el 'Pago de contado / Para no generar intereses' ({simbolo}{saldo_corte_pendiente:,.2f}) "
            "al menos 2 días antes de esa fecha."
        )

    if cargos_tc_quincena > 0:
        consejos.append(
            f"Regla de oro de tu 1ra TC: aunque pagues {simbolo}{cargos_tc_quincena:,.2f} con tarjeta de crédito, "
            "ese dinero NO es dinero extra. Ya quedó apartado en tu cuenta de débito para que cuando llegue la fecha "
            "de pago liquides al 100% sin tocar tu ahorro ni pagar un solo centavo de intereses."
        )

    if limite_credito > 0:
        if porcentaje_uso > 30.0:
            consejos.append(
                f"Tu uso proyectado de la TC es {porcentaje_uso}% del límite ({simbolo}{limite_credito:,.2f}). "
                f"Para construir un historial crediticio excelente, intenta mantener el saldo al corte por debajo del 30% "
                f"({simbolo}{limite_saludable_30:,.2f}) haciendo un abono antes del día {dia_corte}."
            )
        else:
            consejos.append(
                f"Uso de línea de crédito saludable ({porcentaje_uso}% <= 30% recomendado; tope ideal al corte: "
                f"{simbolo}{limite_saludable_30:,.2f})."
            )

    return {
        "nombre": tc.get("nombre", "Tarjeta de Crédito"),
        "proximo_corte": proximo_corte.isoformat(),
        "dias_para_corte": dias_para_corte,
        "proximo_limite_pago": proximo_limite.isoformat(),
        "dias_para_limite_pago": dias_para_limite,
        "vence_en_esta_quincena": vence_en_esta_quincena,
        "cargos_tc_quincena": round(cargos_tc_quincena, 2),
        "pago_saldo_anterior_en_quincena": round(pago_saldo_anterior, 2),
        "apartado_total_tc_en_debito": apartado_total_tc,
        "porcentaje_uso_estimado": porcentaje_uso,
        "limite_saludable_30_pct": limite_saludable_30,
        "consejos": consejos,
    }


def planificar_quincena(
    perfil: dict[str, Any],
    ingreso: float,
    fecha_pago: dt.date,
    gasto_extra: float = 0.0,
    nota_extra: str = "",
    usar_prorrateo_previo: bool = True,
) -> dict[str, Any]:
    """
    Calcula el plan completo de la quincena:
    - Calendario de pagos directos en la ventana actual
    - Apartados prorrateados (50%) de pagos grandes de la siguiente ventana
    - Resumen por método de pago (efectivo, transferencia, débito, tarjeta de crédito)
    - Distribución entre Gastos Libres (salidas) y Ahorro Fuerte
    """
    simbolo = perfil.get("simbolo_moneda", "$")
    moneda = perfil.get("moneda", "USD")
    dias_pago = perfil.get("dias_pago", [15, 30])
    reglas = perfil.get("reglas_liquidez", {})

    piso_libres = float(reglas.get("piso_gastos_libres_quincenal", 500.0))
    suavizar = bool(reglas.get("suavizar_gastos_grandes", True))
    umbral_grande = float(reglas.get("umbral_gasto_grande", 1000.0))
    pct_ahorro_min = float(reglas.get("porcentaje_ahorro_minimo", 15.0))
    pct_ahorro_excedente = float(reglas.get("porcentaje_ahorro_excedente", 70.0))

    ventana = calcular_ventana_pago(fecha_pago, dias_pago)
    f_ini: dt.date = ventana["fecha_inicio"]
    f_prox: dt.date = ventana["proximo_pago"]
    f_sub: dt.date = ventana["subsiguiente_pago"]

    pagos_esta_quincena: list[dict[str, Any]] = []
    apartados_siguiente_quincena: list[dict[str, Any]] = []

    cubetas = {
        "efectivo": 0.0,
        "transferencia": 0.0,
        "debito": 0.0,
        "tc": 0.0,
    }

    for gasto in perfil.get("gastos_fijos", []):
        nombre = gasto["nombre"]
        monto_total = float(gasto["monto"])
        dia_pago = int(gasto["dia_pago"])
        metodo = str(gasto.get("metodo", "debito")).lower()
        if metodo not in cubetas:
            metodo = "debito"

        es_prorrateable = suavizar and (
            bool(gasto.get("prorratear_entre_quincenas", False)) or monto_total >= umbral_grande
        )

        fecha_venc = proxima_ocurrencia_dia(f_ini, dia_pago)

        if f_ini <= fecha_venc < f_prox:
            # Vence en ESTA quincena
            if es_prorrateable and usar_prorrateo_previo:
                monto_de_este_ingreso = round(monto_total / 2.0, 2)
                nota_prorrateo = (
                    f"Pagas {simbolo}{monto_total:,.2f} en total el {fecha_venc.isoformat()} "
                    f"({simbolo}{monto_de_este_ingreso:,.2f} de este pago + "
                    f"{simbolo}{monto_total - monto_de_este_ingreso:,.2f} apartados la quincena pasada)"
                )
            else:
                monto_de_este_ingreso = round(monto_total, 2)
                nota_prorrateo = "Pago completo en esta quincena"

            pagos_esta_quincena.append(
                {
                    "id": gasto.get("id", nombre),
                    "nombre": nombre,
                    "fecha_vencimiento": fecha_venc.isoformat(),
                    "dia_pago": dia_pago,
                    "metodo": metodo,
                    "monto_total_recibo": round(monto_total, 2),
                    "monto_de_este_ingreso": monto_de_este_ingreso,
                    "prorrateado": es_prorrateable and usar_prorrateo_previo,
                    "nota": nota_prorrateo,
                }
            )
            cubetas[metodo] = round(cubetas[metodo] + monto_de_este_ingreso, 2)

        elif f_prox <= fecha_venc < f_sub and es_prorrateable:
            # Vence en la SIGUIENTE quincena, pero es un gasto grande: apartamos el 50% hoy
            mitad = round(monto_total / 2.0, 2)
            apartados_siguiente_quincena.append(
                {
                    "id": gasto.get("id", nombre),
                    "nombre": nombre,
                    "fecha_vencimiento": fecha_venc.isoformat(),
                    "metodo_futuro": metodo,
                    "monto_total_recibo": round(monto_total, 2),
                    "monto_apartar_hoy": mitad,
                    "nota": f"Apartar 50% en débito hoy para no sentir apretada la quincena del {f_prox.isoformat()}",
                }
            )

    pagos_esta_quincena.sort(key=lambda x: x["fecha_vencimiento"])
    apartados_siguiente_quincena.sort(key=lambda x: x["fecha_vencimiento"])

    total_apartados_prorrateo = round(
        sum(a["monto_apartar_hoy"] for a in apartados_siguiente_quincena), 2
    )

    # Analizar Tarjeta de Crédito (si existe)
    tarjetas = perfil.get("tarjetas_credito", [])
    analisis_tc = None
    apartado_tc_en_debito = round(cubetas["tc"], 2)
    pago_tc_saldo_anterior = 0.0

    if tarjetas:
        analisis_tc = analizar_tarjeta_credito(
            tarjetas[0],
            fecha_inicio=f_ini,
            proximo_pago=f_prox,
            cargos_tc_quincena=cubetas["tc"],
            simbolo=simbolo,
        )
        apartado_tc_en_debito = analisis_tc["apartado_total_tc_en_debito"]
        pago_tc_saldo_anterior = analisis_tc["pago_saldo_anterior_en_quincena"]

    # Compromisos obligatorios que salen del ingreso líquido de esta quincena:
    # - Efectivo + Transferencias + Débito + Apartado TC (que cubre los cargos TC + saldo anterior si vence)
    # - Apartados 50% para la próxima quincena
    # - Gasto extra puntual (si el usuario indicó uno)
    total_pagos_directos_no_tc = round(
        cubetas["efectivo"] + cubetas["transferencia"] + cubetas["debito"], 2
    )
    compromisos_totales = round(
        total_pagos_directos_no_tc
        + apartado_tc_en_debito
        + total_apartados_prorrateo
        + gasto_extra,
        2,
    )

    disponible_despues_compromisos = round(ingreso - compromisos_totales, 2)
    alerta_liquidez = None

    # Algoritmo de distribución "Nunca apretado + Ahorro fuerte":
    # 1. Reservamos el ahorro mínimo objetivo si alcanza después de cubrir el piso de gastos libres.
    ahorro_minimo_objetivo = round(ingreso * (pct_ahorro_min / 100.0), 2)

    if disponible_despues_compromisos < 0:
        gastos_libres = 0.0
        ahorro_total = 0.0
        alerta_liquidez = (
            f"ALERTA: Tus compromisos ({simbolo}{compromisos_totales:,.2f}) superan el ingreso "
            f"de esta quincena ({simbolo}{ingreso:,.2f}) por {simbolo}{abs(disponible_despues_compromisos):,.2f}. "
            "Se recomienda pausar temporalmente el apartado de prorrateo o reducir gastos variables."
        )
    elif disponible_despues_compromisos <= piso_libres:
        # Priorizamos que no se quede sin dinero para vivir/comer en la quincena
        gastos_libres = disponible_despues_compromisos
        ahorro_total = 0.0
        alerta_liquidez = (
            f"Quincena ajustada: después de pagos y apartados quedan {simbolo}{disponible_despues_compromisos:,.2f}, "
            f"que se asignan íntegros a tu piso de tranquilidad (gastos libres)."
        )
    elif disponible_despues_compromisos <= (piso_libres + ahorro_minimo_objetivo):
        gastos_libres = piso_libres
        ahorro_total = round(disponible_despues_compromisos - piso_libres, 2)
    else:
        # Hay excedente por encima del piso de gastos libres + ahorro mínimo
        excedente = round(
            disponible_despues_compromisos - piso_libres - ahorro_minimo_objetivo, 2
        )
        ahorro_adicional = round(excedente * (pct_ahorro_excedente / 100.0), 2)
        libres_adicional = round(excedente - ahorro_adicional, 2)

        ahorro_total = round(ahorro_minimo_objetivo + ahorro_adicional, 2)
        gastos_libres = round(piso_libres + libres_adicional, 2)

    porcentaje_ahorro_real = round((ahorro_total / ingreso) * 100.0, 2) if ingreso > 0 else 0.0

    # Desglose de metas de ahorro
    desglose_ahorro: list[dict[str, Any]] = []
    metas = perfil.get("metas_ahorro", [])
    acumulado_metas = 0.0
    for idx, meta in enumerate(metas):
        pct_meta = float(meta.get("porcentaje_del_ahorro", 100.0 / max(1, len(metas))))
        if idx == len(metas) - 1:
            monto_meta = round(max(0.0, ahorro_total - acumulado_metas), 2)
        else:
            monto_meta = round(ahorro_total * (pct_meta / 100.0), 2)
            acumulado_metas = round(acumulado_metas + monto_meta, 2)
        desglose_ahorro.append(
            {
                "nombre": meta.get("nombre", f"Meta {idx + 1}"),
                "porcentaje": pct_meta,
                "monto": monto_meta,
            }
        )

    # Acciones exactas por método de pago para el día de depósito
    saldo_dejar_en_debito = round(
        cubetas["debito"]
        + apartado_tc_en_debito
        + total_apartados_prorrateo
        + gastos_libres
        + gasto_extra,
        2,
    )

    acciones_dia_pago = {
        "retirar_efectivo_cajero": cubetas["efectivo"],
        "transferir_hoy_o_en_fecha": cubetas["transferencia"],
        "mover_a_cuenta_ahorro_fuerte": ahorro_total,
        "dejar_en_cuenta_debito_total": saldo_dejar_en_debito,
        "detalle_en_debito": {
            "cargos_debito_fijos": cubetas["debito"],
            "apartado_intocable_tc": apartado_tc_en_debito,
            "apartado_prorrateo_proxima_quincena": total_apartados_prorrateo,
            "gasto_extra_reservado": round(gasto_extra, 2),
            "disponible_gastos_libres_y_salidas": gastos_libres,
        },
    }

    verificacion_suma = round(
        cubetas["efectivo"]
        + cubetas["transferencia"]
        + ahorro_total
        + saldo_dejar_en_debito,
        2,
    )

    return {
        "meta": {
            "usuario": perfil.get("nombre_usuario", "Usuario"),
            "moneda": moneda,
            "simbolo": simbolo,
            "fecha_pago": f_ini.isoformat(),
            "proximo_pago": f_prox.isoformat(),
            "dias_ventana": ventana["dias_ventana"],
            "codigo_periodo": ventana["codigo_periodo"],
        },
        "resumen_montos": {
            "ingreso_quincena": round(ingreso, 2),
            "pagos_directos_no_tc": total_pagos_directos_no_tc,
            "apartado_tc_en_debito": apartado_tc_en_debito,
            "pago_tc_saldo_anterior": pago_tc_saldo_anterior,
            "apartados_prorrateo_proxima_quincena": total_apartados_prorrateo,
            "gasto_extra": round(gasto_extra, 2),
            "nota_gasto_extra": nota_extra,
            "gastos_libres_salidas": gastos_libres,
            "ahorro_fuerte_total": ahorro_total,
            "porcentaje_ahorro_real": porcentaje_ahorro_real,
            "verificacion_suma_exacta": verificacion_suma,
            "diferencia_redondeo": round(ingreso - verificacion_suma, 2),
        },
        "alerta_liquidez": alerta_liquidez,
        "cubetas_metodo_pago": cubetas,
        "acciones_dia_pago": acciones_dia_pago,
        "calendario_pagos_quincena": pagos_esta_quincena,
        "apartados_prorrateo": apartados_siguiente_quincena,
        "desglose_ahorro": desglose_ahorro,
        "analisis_tarjeta_credito": analisis_tc,
    }


def renderizar_markdown(plan: dict[str, Any]) -> str:
    """Convierte el resultado estructurado del motor en un reporte Markdown claro."""
    m = plan["meta"]
    r = plan["resumen_montos"]
    a = plan["acciones_dia_pago"]
    s = m["simbolo"]

    lines: list[str] = [
        f"# Plan Quincenal Arceus — {m['codigo_periodo']}",
        "",
        f"- **Fecha de ingreso:** `{m['fecha_pago']}` → **Próximo pago:** `{m['proximo_pago']}` ({m['dias_ventana']} días)",
        f"- **Ingreso recibido:** **{s}{r['ingreso_quincena']:,.2f} {m['moneda']}**",
        f"- **Ahorro Fuerte logrado:** **{s}{r['ahorro_fuerte_total']:,.2f}** (`{r['porcentaje_ahorro_real']}%` del ingreso)",
        f"- **Disponible para gastos libres / salidas:** **{s}{r['gastos_libres_salidas']:,.2f}**",
        "",
    ]

    if plan.get("alerta_liquidez"):
        lines.extend([f"> ⚠️ **{plan['alerta_liquidez']}**", ""])

    lines.extend(
        [
            "## 1. Acciones Inmediatas (Qué hacer hoy con tu dinero)",
            "",
            "| Acción / Cubeta | Monto | Instrucción exacta |",
            "| :--- | ---: | :--- |",
            f"| **1. Mover a Ahorro Fuerte** | **{s}{a['mover_a_cuenta_ahorro_fuerte']:,.2f}** | Pásalo hoy mismo a tu cuenta/apartado de ahorro (págate a ti primero). |",
            f"| **2. Retirar en Efectivo** | **{s}{a['retirar_efectivo_cajero']:,.2f}** | Retíralo en una sola visita al cajero para tus pagos en efectivo de la quincena. |",
            f"| **3. Transferencias Fijas** | **{s}{a['transferir_hoy_o_en_fecha']:,.2f}** | Para tus pagos por transferencia bancaria de esta quincena. |",
            f"| **4. Dejar en Cuenta de Débito** | **{s}{a['dejar_en_cuenta_debito_total']:,.2f}** | Todo lo que se queda en tu cuenta (ver desglose de blindaje abajo). |",
            f"| **Total cuadrado al centavo** | **{s}{r['verificacion_suma_exacta']:,.2f}** | Cuadra al 100% con tu ingreso de `{s}{r['ingreso_quincena']:,.2f}`. |",
            "",
            "### Desglose de lo que se queda en tu Tarjeta de Débito",
            f"- **Cargos fijos con Débito:** `{s}{a['detalle_en_debito']['cargos_debito_fijos']:,.2f}`",
            f"- **Apartado INTOCABLE para pagar Tarjeta de Crédito:** `{s}{a['detalle_en_debito']['apartado_intocable_tc']:,.2f}`",
            f"- **Apartado 50% (Anti-Apretón) para pagos fuertes de la próxima quincena:** `{s}{a['detalle_en_debito']['apartado_prorrateo_proxima_quincena']:,.2f}`",
        ]
    )

    if r["gasto_extra"] > 0:
        nota = f" ({r['nota_gasto_extra']})" if r["nota_gasto_extra"] else ""
        lines.append(
            f"- **Reserva para gasto extra de esta quincena{nota}:** `{s}{r['gasto_extra']:,.2f}`"
        )

    lines.extend(
        [
            f"- **Libre para tus salidas y gastos diarios (sin culpa):** **`{s}{a['detalle_en_debito']['disponible_gastos_libres_y_salidas']:,.2f}`**",
            "",
            "## 2. Calendario de Pagos de Esta Quincena",
            "",
        ]
    )

    if plan["calendario_pagos_quincena"]:
        lines.extend(
            [
                "| Fecha límite | Gasto fijo | Método | Recibo total | Sale de esta quincena | Nota |",
                "| :--- | :--- | :--- | ---: | ---: | :--- |",
            ]
        )
        for p in plan["calendario_pagos_quincena"]:
            metodo_badge = p["metodo"].upper()
            lines.append(
                f"| `{p['fecha_vencimiento']}` | {p['nombre']} | `{metodo_badge}` | "
                f"{s}{p['monto_total_recibo']:,.2f} | **{s}{p['monto_de_este_ingreso']:,.2f}** | {p['nota']} |"
            )
    else:
        lines.append("_No hay pagos fijos con vencimiento directo dentro de esta ventana._")

    lines.append("")

    if plan["apartados_prorrateo"]:
        lines.extend(
            [
                "## 3. Blindaje Anti-Apretón (Apartados 50% para la Próxima Quincena)",
                "",
                "| Vence el | Gasto fuerte | Método futuro | Recibo total | Apartar HOY (50%) | Propósito |",
                "| :--- | :--- | :--- | ---: | ---: | :--- |",
            ]
        )
        for ap in plan["apartados_prorrateo"]:
            lines.append(
                f"| `{ap['fecha_vencimiento']}` | {ap['nombre']} | `{ap['metodo_futuro'].upper()}` | "
                f"{s}{ap['monto_total_recibo']:,.2f} | **{s}{ap['monto_apartar_hoy']:,.2f}** | {ap['nota']} |"
            )
        lines.append("")

    if plan["desglose_ahorro"]:
        lines.extend(
            [
                "## 4. Distribución de tu Ahorro Fuerte",
                "",
                "| Meta de Ahorro | % del Ahorro | Monto a depositar hoy |",
                "| :--- | ---: | ---: |",
            ]
        )
        for meta in plan["desglose_ahorro"]:
            lines.append(
                f"| {meta['nombre']} | `{meta['porcentaje']:.0f}%` | **{s}{meta['monto']:,.2f}** |"
            )
        lines.append("")

    tc = plan.get("analisis_tarjeta_credito")
    if tc:
        lines.extend(
            [
                f"## 5. Estrategia para tu Tarjeta de Crédito ({tc['nombre']})",
                "",
                f"- **Próxima fecha de corte:** `{tc['proximo_corte']}` (en **{tc['dias_para_corte']} días**)",
                f"- **Próxima fecha límite de pago:** `{tc['proximo_limite_pago']}` (en **{tc['dias_para_limite_pago']} días**)",
                f"- **Gastos fijos que pagarás con TC esta quincena:** `{s}{tc['cargos_tc_quincena']:,.2f}`",
                f"- **Apartado total en Débito para ser Totalero (0% intereses):** **`{s}{tc['apartado_total_tc_en_debito']:,.2f}`**",
                f"- **Uso proyectado de línea de crédito:** `{tc['porcentaje_uso_estimado']}%` (tope saludable 30%: `{s}{tc['limite_saludable_30_pct']:,.2f}`)",
                "",
                "### Consejos de Arceus para tu TC en esta quincena:",
            ]
        )
        for c in tc["consejos"]:
            lines.append(f"- {c}")
        lines.append("")

    return "\n".join(lines)


def guardar_reporte_e_historial(plan: dict[str, Any], markdown_text: str) -> dict[str, str]:
    """Guarda el reporte Markdown en `reportes/` y registra la fila en `historial/quincenas.csv`."""
    REPORTES_DIR.mkdir(parents=True, exist_ok=True)
    HISTORIAL_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    m = plan["meta"]
    r = plan["resumen_montos"]
    reporte_path = REPORTES_DIR / f"{m['codigo_periodo']}_{m['fecha_pago']}.md"
    reporte_path.write_text(markdown_text, encoding="utf-8")

    existe_csv = HISTORIAL_CSV_PATH.exists()
    with HISTORIAL_CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not existe_csv:
            writer.writerow(
                [
                    "fecha",
                    "periodo",
                    "ingreso",
                    "pagos_directos",
                    "apartados_prorrateo",
                    "apartado_tc",
                    "gastos_libres",
                    "ahorro_total",
                    "porcentaje_ahorro",
                    "notas",
                ]
            )
        writer.writerow(
            [
                m["fecha_pago"],
                m["codigo_periodo"],
                f"{r['ingreso_quincena']:.2f}",
                f"{r['pagos_directos_no_tc']:.2f}",
                f"{r['apartados_prorrateo_proxima_quincena']:.2f}",
                f"{r['apartado_tc_en_debito']:.2f}",
                f"{r['gastos_libres_salidas']:.2f}",
                f"{r['ahorro_fuerte_total']:.2f}",
                f"{r['porcentaje_ahorro_real']:.2f}",
                r["nota_gasto_extra"] or "Plan quincenal Arceus",
            ]
        )

    return {
        "reporte_guardado": str(reporte_path),
        "historial_actualizado": str(HISTORIAL_CSV_PATH),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Motor determinista de planificación financiera quincenal Arceus."
    )
    parser.add_argument(
        "--check-setup",
        action="store_true",
        help="Verifica si el perfil del usuario ya existe o si se debe iniciar la entrevista inicial.",
    )
    parser.add_argument(
        "--perfil",
        type=Path,
        default=DEFAULT_PROFILE_PATH,
        help="Ruta al archivo JSON de perfil del usuario (por defecto: perfil/usuario.json).",
    )
    parser.add_argument(
        "--usar-ejemplo",
        action="store_true",
        help="Usa perfil/usuario.example.json para pruebas o demostraciones.",
    )
    parser.add_argument(
        "--ingreso",
        type=float,
        help="Monto recibido en la quincena/depósito actual.",
    )
    parser.add_argument(
        "--fecha",
        type=str,
        default=dt.date.today().isoformat(),
        help="Fecha del depósito en formato YYYY-MM-DD (por defecto: hoy).",
    )
    parser.add_argument(
        "--gasto-extra",
        type=float,
        default=0.0,
        help="Monto de algún gasto extraordinario o salida especial en esta quincena.",
    )
    parser.add_argument(
        "--nota-extra",
        type=str,
        default="",
        help="Descripción del gasto extraordinario.",
    )
    parser.add_argument(
        "--sin-prorrateo-previo",
        action="store_true",
        help="Indica que es la primera quincena usando Arceus y aún no hay 50%% apartado de la quincena anterior.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime la salida en formato JSON estructurado.",
    )
    parser.add_argument(
        "--guardar",
        action="store_true",
        help="Guarda el reporte en reportes/ y agrega el registro a historial/quincenas.csv.",
    )

    args = parser.parse_args(argv)
    perfil_path = EXAMPLE_PROFILE_PATH if args.usar_ejemplo else args.perfil

    if args.check_setup:
        if perfil_path.exists():
            try:
                data = json.loads(perfil_path.read_text(encoding="utf-8"))
                print(
                    json.dumps(
                        {
                            "configurado": True,
                            "modo": "PLANIFICACION_QUINCENAL",
                            "perfil_path": str(perfil_path),
                            "usuario": data.get("nombre_usuario"),
                            "moneda": data.get("moneda"),
                            "gastos_fijos_registrados": len(data.get("gastos_fijos", [])),
                            "tarjetas_registradas": len(data.get("tarjetas_credito", [])),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 0
            except Exception as exc:
                print(
                    json.dumps(
                        {
                            "configurado": False,
                            "modo": "ENTREVISTA_INICIAL",
                            "error": f"El archivo de perfil existe pero tiene un error de formato: {exc}",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 1
        else:
            print(
                json.dumps(
                    {
                        "configurado": False,
                        "modo": "ENTREVISTA_INICIAL",
                        "mensaje": (
                            "No existe perfil/usuario.json. Arceus debe iniciar la entrevista "
                            "paso a paso para conocer la situación financiera del usuario."
                        ),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

    if not perfil_path.exists():
        print(
            json.dumps(
                {
                    "error": "PERFIL_NO_CONFIGURADO",
                    "modo_requerido": "ENTREVISTA_INICIAL",
                    "mensaje": (
                        f"No se encontró {perfil_path}. Ejecuta primero la entrevista inicial "
                        "de Arceus (/setup) para crear el perfil financiero del usuario."
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    if args.ingreso is None or args.ingreso <= 0:
        parser.error("Debes indicar un monto válido con --ingreso <MONTO>.")

    fecha_pago = dt.date.fromisoformat(args.fecha)
    perfil = json.loads(perfil_path.read_text(encoding="utf-8"))

    plan = planificar_quincena(
        perfil=perfil,
        ingreso=args.ingreso,
        fecha_pago=fecha_pago,
        gasto_extra=args.gasto_extra,
        nota_extra=args.nota_extra,
        usar_prorrateo_previo=not args.sin_prorrateo_previo,
    )
    md = renderizar_markdown(plan)

    if args.guardar and not args.usar_ejemplo:
        archivos = guardar_reporte_e_historial(plan, md)
        plan["archivos_generados"] = archivos

    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(md)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
