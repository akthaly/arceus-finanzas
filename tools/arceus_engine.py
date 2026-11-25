#!/usr/bin/env python3
"""
Motor determinista de Arceus Finanzas (tools/arceus_engine.py).
Optimizado para bajo consumo de tokens: resuelve en 1 sola llamada:
1. Planificación quincenal exacta (--ingreso)
2. Evaluador de compras + Ventana de Oro TC + Calendario Festivo Guatemala (--evaluar-compra)
3. Verificación de estado de configuración (--check-setup)
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
    last_day = calendar.monthrange(year, month)[1]
    return dt.date(year, month, min(max(1, day), last_day))


def next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def prev_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def proxima_ocurrencia_dia(desde: dt.date, dia_mes: int) -> dt.date:
    cand_actual = clamp_day(desde.year, desde.month, dia_mes)
    if cand_actual >= desde:
        return cand_actual
    ny, nm = next_month(desde.year, desde.month)
    return clamp_day(ny, nm, dia_mes)


def calcular_ciclo_tc_para_fecha(
    fecha_compra: dt.date, dia_corte: int, dia_limite_pago: int
) -> dict[str, Any]:
    corte_compra = proxima_ocurrencia_dia(fecha_compra, dia_corte)
    limite_pago = proxima_ocurrencia_dia(corte_compra + dt.timedelta(days=1), dia_limite_pago)
    dias_financiamiento = (limite_pago - fecha_compra).days
    return {
        "fecha_compra": fecha_compra.isoformat(),
        "fecha_corte": corte_compra.isoformat(),
        "fecha_limite_pago": limite_pago.isoformat(),
        "dias_financiamiento_gratis": dias_financiamiento,
    }


def detectar_categoria_compra(nombre_compra: str, categoria_explicita: str = "") -> str:
    if categoria_explicita and categoria_explicita != "auto":
        return categoria_explicita.lower()
    txt = nombre_compra.lower()
    if any(
        k in txt
        for k in ("ropa", "zapatos", "tenis", "camisa", "pantalon", "outfit", "vestido", "chumpa", "calzado")
    ):
        return "ropa"
    if any(
        k in txt
        for k in (
            "telefono",
            "celular",
            "iphone",
            "laptop",
            "computadora",
            "pc",
            "monitor",
            "audifonos",
            "tv",
            "tele",
            "consola",
            "ipad",
            "tablet",
            "tecnologia",
        )
    ):
        return "tecnologia"
    if any(k in txt for k in ("regalo", "navidad", "amigo secreto", "juguetes")):
        return "regalos"
    return "general"


def analizar_temporadas_festivas_gt(
    fecha_actual: dt.date,
    categoria: str,
    dia_corte: int,
    dia_limite_pago: int,
) -> dict[str, Any]:
    """
    Evalúa el calendario comercial y festivo de Guatemala (Black Friday/Black Weekend,
    Temporada de Aguinaldo y Navidad, Liquidaciones de Fin de Año e Inicios de Enero,
    y Bono 14 en Julio) cruzado con el día de corte de la Tarjeta de Crédito del usuario.
    """
    year = fecha_actual.year
    next_yr = year + 1 if fecha_actual.month >= 11 else year

    # Fechas clave de fin de año e inicio de año en Guatemala
    corte_dic = clamp_day(year if fecha_actual.month >= 11 else year, 12, dia_corte)
    post_corte_dic = corte_dic + dt.timedelta(days=1)
    corte_ene = clamp_day(next_yr, 1, dia_corte)
    post_corte_ene = corte_ene + dt.timedelta(days=1)

    ciclo_bf = calcular_ciclo_tc_para_fecha(dt.date(year, 11, 27), dia_corte, dia_limite_pago)
    ciclo_post_dic = calcular_ciclo_tc_para_fecha(post_corte_dic, dia_corte, dia_limite_pago)
    ciclo_post_ene = calcular_ciclo_tc_para_fecha(post_corte_ene, dia_corte, dia_limite_pago)

    ventanas_festivas: list[dict[str, str]] = []

    if categoria == "ropa":
        estrategia_temporada = (
            "ESTRATEGIA ROPA GUATEMALA (Regla 30/70): En Guatemala, del 10 al 24 de diciembre (entrada del Aguinaldo) "
            "la ropa está en su PRECIO MÁS CARO del año. "
            f"Divide tu compra: 1) Usa el 30% de tu presupuesto el {post_corte_dic.isoformat()} (1 día después de tu corte de TC) "
            "solo para lo que quieras estrenar en Navidad/Año Nuevo. "
            f"2) Guarda el 70% para la Liquidación de Inicios de Año (desde el {post_corte_ene.isoformat()}, post-corte de enero), "
            "cuando las tiendas en GT rematan inventario con 30% a 60% de descuento real y pagas hasta marzo."
        )
        ventanas_festivas = [
            {
                "temporada": "1. Black Friday / Black Weekend GT (Fin de Nov)",
                "fechas": f"{year}-11-27 al {year}-11-30",
                "descuento_tipico_gt": "15% a 30% (seleccionados)",
                "impacto_tc": f"Corta el {ciclo_bf['fecha_corte']} -> Pagas el {ciclo_bf['fecha_limite_pago']} ({ciclo_bf['dias_financiamiento_gratis']}d)",
                "veredicto": "⚠️ Solo si hay >=30% real o NeoCuotas 0% (porque toca pagarlo el 1 de enero).",
            },
            {
                "temporada": "2. Ventana Post-Corte Pre-Aguinaldo (Inicios Dic)",
                "fechas": f"{post_corte_dic.isoformat()} al {year}-12-11",
                "descuento_tipico_gt": "Precio normal / Promos bancarias",
                "impacto_tc": f"Corta el {ciclo_post_dic['fecha_corte']} -> Pagas el {ciclo_post_dic['fecha_limite_pago']} ({ciclo_post_dic['dias_financiamiento_gratis']}d)",
                "veredicto": "✅ Ideal para comprar SOLO el estreno de Navidad/Año Nuevo (56 días sin interés).",
            },
            {
                "temporada": "3. Fiebre de Aguinaldo y Navidad (12 al 24 Dic)",
                "fechas": f"{year}-12-12 al {year}-12-24",
                "descuento_tipico_gt": "0% (Precios más altos del año en GT)",
                "impacto_tc": f"Corta el {ciclo_post_dic['fecha_corte']} -> Pagas el {ciclo_post_dic['fecha_limite_pago']}",
                "veredicto": "❌ EVITAR: Centros comerciales llenos y ropa a precio completo sin rebaja.",
            },
            {
                "temporada": "4. Liquidación Fin de Año e Inicios de Enero (Rebajas GT)",
                "fechas": f"{year}-12-26 y {post_corte_ene.isoformat()} al {next_yr}-01-20",
                "descuento_tipico_gt": "30% a 60% OFF (Liquidación total)",
                "impacto_tc": f"Comprando el {post_corte_ene.isoformat()} pagas hasta {ciclo_post_ene['fecha_limite_pago']} ({ciclo_post_ene['dias_financiamiento_gratis']}d)",
                "veredicto": "⭐ MEJOR MOMENTO DEL AÑO PARA ROPA: Mitad de precio + pagas hasta marzo.",
            },
        ]
    elif categoria == "tecnologia":
        estrategia_temporada = (
            "ESTRATEGIA TECNOLOGÍA GUATEMALA: Para electrónica y tecnología, los mejores precios reales en GT "
            "están en Black Friday / Cyber Monday (última semana de noviembre) y en Liquidaciones de Enero "
            "(cuando liquidan modelos del año anterior). Si compras en Black Friday y tu corte es el día 6, "
            "pídelo en NeoCuotas/Visacuotas 0% interés para que no te golpee el pago de contado el 1 de enero."
        )
        ventanas_festivas = [
            {
                "temporada": "1. Black Friday / Cyber Monday GT",
                "fechas": f"{year}-11-27 al {year}-11-30",
                "descuento_tipico_gt": "20% a 40% OFF + Cuotas 0%",
                "impacto_tc": f"Corta el {ciclo_bf['fecha_corte']} -> Pagas el {ciclo_bf['fecha_limite_pago']}",
                "veredicto": "⭐ MEJOR PRECIO EN TECH: Aprovechar con NeoCuotas 0% interés.",
            },
            {
                "temporada": "2. Post-Corte Diciembre",
                "fechas": f"Desde el {post_corte_dic.isoformat()}",
                "descuento_tipico_gt": "10% a 20% (combos navideños)",
                "impacto_tc": f"Pagas hasta el {ciclo_post_dic['fecha_limite_pago']} ({ciclo_post_dic['dias_financiamiento_gratis']}d gratis)",
                "veredicto": "✅ Mejor financiamiento si vas a pagar en 1 solo pago al corte.",
            },
            {
                "temporada": "3. Liquidación de Inventario Enero (Inicios de Año)",
                "fechas": f"{post_corte_ene.isoformat()} al {next_yr}-01-25",
                "descuento_tipico_gt": "25% a 45% en modelos {year}",
                "impacto_tc": f"Pagas hasta el {ciclo_post_ene['fecha_limite_pago']} ({ciclo_post_ene['dias_financiamiento_gratis']}d gratis)",
                "veredicto": "⭐ Excelente para laptops/monitores con 50+ días de financiamiento.",
            },
        ]
    else:
        estrategia_temporada = (
            "ESTRATEGIA DE TEMPORADA GUATEMALA: Evita comprar entre el 12 y el 24 de diciembre (efecto Aguinaldo: "
            "precios inflados y poca disponibilidad). Tus dos mejores ventanas son: "
            f"1) El {post_corte_dic.isoformat()} (1 día después de tu corte de diciembre, ganas ~55 días sin interés). "
            f"2) A partir del {post_corte_ene.isoformat()} (liquidaciones de inicio de año en Guatemala con descuentos de 30%-50%)."
        )
        ventanas_festivas = [
            {
                "temporada": "1. Black Weekend GT (Fin de Nov)",
                "fechas": f"{year}-11-27 al {year}-11-30",
                "descuento_tipico_gt": "15% a 35% OFF",
                "impacto_tc": f"Corta el {ciclo_bf['fecha_corte']} -> Pagas el {ciclo_bf['fecha_limite_pago']}",
                "veredicto": "✅ Bueno si usas cuotas 0% interés (en 1 pago vence el 1 de enero).",
            },
            {
                "temporada": "2. Ventana de Oro Post-Corte Diciembre",
                "fechas": f"{post_corte_dic.isoformat()} al {year}-12-11",
                "descuento_tipico_gt": "Promos pre-navideñas",
                "impacto_tc": f"Pagas hasta el {ciclo_post_dic['fecha_limite_pago']} ({ciclo_post_dic['dias_financiamiento_gratis']}d gratis)",
                "veredicto": "⭐ Mejor fecha en diciembre antes de la inflación del Aguinaldo.",
            },
            {
                "temporada": "3. Liquidación de Inicio de Año (Enero GT)",
                "fechas": f"{post_corte_ene.isoformat()} al {next_yr}-01-20",
                "descuento_tipico_gt": "30% a 50% OFF post-fiestas",
                "impacto_tc": f"Pagas hasta el {ciclo_post_ene['fecha_limite_pago']} ({ciclo_post_ene['dias_financiamiento_gratis']}d gratis)",
                "veredicto": "⭐ MEJOR PRECIO + FINANCIAMIENTO si la compra puede esperar a enero.",
            },
        ]

    return {
        "pais": "Guatemala",
        "categoria_detectada": categoria,
        "estrategia_temporada_gt": estrategia_temporada,
        "comparativa_fechas_festivas": ventanas_festivas,
    }


def calcular_ventana_pago(
    fecha_actual: dt.date,
    dias_pago: list[int],
    frecuencia_pago: str = "quincenal",
) -> dict[str, Any]:
    es_mensual = frecuencia_pago.lower() == "mensual" or len(set(dias_pago)) == 1
    dias_ordenados = sorted(set(dias_pago)) or ([30] if es_mensual else [15, 30])
    candidatos: list[dt.date] = []
    y, m = prev_month(fecha_actual.year, fecha_actual.month)
    for _ in range(4):
        for d in dias_ordenados:
            candidatos.append(clamp_day(y, m, d))
        y, m = next_month(y, m)
    candidatos = sorted(set(candidatos))

    futuros = [c for c in candidatos if (c - fecha_actual).days > 4]
    proximo_pago = futuros[0]
    subsiguiente_pago = futuros[1]

    if es_mensual:
        codigo_periodo = f"{fecha_actual.year:04d}-{fecha_actual.month:02d}-M"
    else:
        quincena_num = 1 if fecha_actual.day <= 20 else 2
        codigo_periodo = f"{fecha_actual.year:04d}-{fecha_actual.month:02d}-Q{quincena_num}"

    return {
        "es_mensual": es_mensual,
        "pagos_por_mes": 1 if es_mensual else 2,
        "fecha_inicio": fecha_actual,
        "proximo_pago": proximo_pago,
        "subsiguiente_pago": subsiguiente_pago,
        "dias_ventana": (proximo_pago - fecha_actual).days,
        "codigo_periodo": codigo_periodo,
    }


def analizar_tarjeta_credito(
    tc: dict[str, Any],
    fecha_inicio: dt.date,
    proximo_pago: dt.date,
    cargos_tc_quincena: float,
    simbolo: str,
) -> dict[str, Any]:
    dia_corte = int(tc.get("dia_corte", 10))
    dia_limite = int(tc.get("dia_limite_pago", 28))
    limite_credito = float(tc.get("limite_credito", 0.0))
    saldo_corte_pendiente = float(tc.get("saldo_al_corte_pendiente", 0.0))
    cuotas_fijas_mes = float(tc.get("cuotas_fijas_mes", 0.0))

    proximo_corte = proxima_ocurrencia_dia(fecha_inicio, dia_corte)
    proximo_limite = proxima_ocurrencia_dia(fecha_inicio, dia_limite)
    fecha_oro_compra = proximo_corte + dt.timedelta(days=1)
    ciclo_hoy = calcular_ciclo_tc_para_fecha(fecha_inicio, dia_corte, dia_limite)
    ciclo_oro = calcular_ciclo_tc_para_fecha(fecha_oro_compra, dia_corte, dia_limite)

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
    if dias_para_corte <= 5:
        consejos.append(
            f"Corte próximo ({proximo_corte.isoformat()}, en {dias_para_corte}d). "
            f"Mejor fecha para compras grandes: desde el {fecha_oro_compra.isoformat()} "
            f"(ganas {ciclo_oro['dias_financiamiento_gratis']}d sin intereses, pagas hasta {ciclo_oro['fecha_limite_pago']})."
        )
    else:
        consejos.append(
            f"Si compras hoy tienes {ciclo_hoy['dias_financiamiento_gratis']}d sin intereses (pagas el {ciclo_hoy['fecha_limite_pago']}). "
            f"Próxima ventana de oro (~{ciclo_oro['dias_financiamiento_gratis']}d): {fecha_oro_compra.isoformat()}."
        )

    if vence_en_esta_quincena and saldo_corte_pendiente > 0:
        consejos.append(
            f"TOTALERO: Liquida {simbolo}{saldo_corte_pendiente:,.2f} antes del {proximo_limite.isoformat()}."
        )

    if cargos_tc_quincena > 0:
        consejos.append(
            f"Apartado TC en débito: {simbolo}{cargos_tc_quincena:,.2f} reservados para pagar 0% intereses."
        )

    if limite_credito > 0:
        consejos.append(
            f"Uso de línea: {porcentaje_uso}% (tope saludable 30%: {simbolo}{limite_saludable_30:,.2f})."
        )

    return {
        "nombre": tc.get("nombre", "Tarjeta de Crédito"),
        "proximo_corte": proximo_corte.isoformat(),
        "dias_para_corte": dias_para_corte,
        "proximo_limite_pago": proximo_limite.isoformat(),
        "dias_para_limite_pago": dias_para_limite,
        "ventana_oro_compras": fecha_oro_compra.isoformat(),
        "dias_financiamiento_hoy": ciclo_hoy["dias_financiamiento_gratis"],
        "dias_financiamiento_ventana_oro": ciclo_oro["dias_financiamiento_gratis"],
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
    simbolo = perfil.get("simbolo_moneda", "$")
    moneda = perfil.get("moneda", "USD")
    frecuencia_pago = str(perfil.get("frecuencia_pago", "quincenal")).lower()
    dias_pago = perfil.get("dias_pago", [30] if frecuencia_pago == "mensual" else [15, 30])
    reglas = perfil.get("reglas_liquidez", {})

    piso_libres = float(reglas.get("piso_gastos_libres_quincenal", 500.0))
    suavizar = bool(reglas.get("suavizar_gastos_grandes", True))
    umbral_grande = float(reglas.get("umbral_gasto_grande", 1000.0))
    pct_ahorro_min = float(reglas.get("porcentaje_ahorro_minimo", 15.0))
    pct_ahorro_excedente = float(reglas.get("porcentaje_ahorro_excedente", 70.0))

    ventana = calcular_ventana_pago(fecha_pago, dias_pago, frecuencia_pago)
    es_mensual: bool = ventana["es_mensual"]
    f_ini: dt.date = ventana["fecha_inicio"]
    f_prox: dt.date = ventana["proximo_pago"]
    f_sub: dt.date = ventana["subsiguiente_pago"]

    pagos_esta_quincena: list[dict[str, Any]] = []
    apartados_siguiente_quincena: list[dict[str, Any]] = []
    cubetas = {"efectivo": 0.0, "transferencia": 0.0, "debito": 0.0, "tc": 0.0}

    for gasto in perfil.get("gastos_fijos", []):
        nombre = gasto["nombre"]
        monto_total = float(gasto["monto"])
        dia_pago = int(gasto["dia_pago"])
        metodo = str(gasto.get("metodo", "debito")).lower()
        if metodo not in cubetas:
            metodo = "debito"

        # En pago mensual todos los gastos del mes se cubren al 100% en este ingreso (no se dividen entre 2 quincenas)
        es_prorrateable = (not es_mensual) and suavizar and (
            bool(gasto.get("prorratear_entre_quincenas", False)) or monto_total >= umbral_grande
        )
        fecha_venc = proxima_ocurrencia_dia(f_ini, dia_pago)

        if f_ini <= fecha_venc < f_prox:
            if es_prorrateable and usar_prorrateo_previo:
                monto_de_este_ingreso = round(monto_total / 2.0, 2)
                nota_prorrateo = (
                    f"50% hoy ({simbolo}{monto_de_este_ingreso:,.2f}) + 50% apartado previo"
                )
            else:
                monto_de_este_ingreso = round(monto_total, 2)
                nota_prorrateo = "100% este periodo"

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
            mitad = round(monto_total / 2.0, 2)
            apartados_siguiente_quincena.append(
                {
                    "id": gasto.get("id", nombre),
                    "nombre": nombre,
                    "fecha_vencimiento": fecha_venc.isoformat(),
                    "metodo_futuro": metodo,
                    "monto_total_recibo": round(monto_total, 2),
                    "monto_apartar_hoy": mitad,
                    "nota": f"Apartar 50% para quincena {f_prox.isoformat()}",
                }
            )

    pagos_esta_quincena.sort(key=lambda x: x["fecha_vencimiento"])
    apartados_siguiente_quincena.sort(key=lambda x: x["fecha_vencimiento"])

    total_apartados_prorrateo = round(
        sum(a["monto_apartar_hoy"] for a in apartados_siguiente_quincena), 2
    )

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
    ahorro_minimo_objetivo = round(ingreso * (pct_ahorro_min / 100.0), 2)

    if disponible_despues_compromisos < 0:
        gastos_libres = 0.0
        ahorro_total = 0.0
        alerta_liquidez = (
            f"ALERTA: Compromisos ({simbolo}{compromisos_totales:,.2f}) superan ingreso "
            f"({simbolo}{ingreso:,.2f}) por {simbolo}{abs(disponible_despues_compromisos):,.2f}."
        )
    elif disponible_despues_compromisos <= piso_libres:
        gastos_libres = disponible_despues_compromisos
        ahorro_total = 0.0
        alerta_liquidez = (
            f"Quincena ajustada: {simbolo}{disponible_despues_compromisos:,.2f} asignados a gastos libres."
        )
    elif disponible_despues_compromisos <= (piso_libres + ahorro_minimo_objetivo):
        gastos_libres = piso_libres
        ahorro_total = round(disponible_despues_compromisos - piso_libres, 2)
    else:
        excedente = round(
            disponible_despues_compromisos - piso_libres - ahorro_minimo_objetivo, 2
        )
        ahorro_adicional = round(excedente * (pct_ahorro_excedente / 100.0), 2)
        libres_adicional = round(excedente - ahorro_adicional, 2)
        ahorro_total = round(ahorro_minimo_objetivo + ahorro_adicional, 2)
        gastos_libres = round(piso_libres + libres_adicional, 2)

    porcentaje_ahorro_real = round((ahorro_total / ingreso) * 100.0, 2) if ingreso > 0 else 0.0

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
        cubetas["efectivo"] + cubetas["transferencia"] + ahorro_total + saldo_dejar_en_debito,
        2,
    )

    # Para usuarios de pago mensual, dividimos sus gastos libres en 4 semanas ("Blindaje 4 Semanas")
    # para que no gasten toda su liquidez en la semana 1 y lleguen holgados a fin de mes.
    presupuesto_semanal_libres = round(gastos_libres / (4.0 if es_mensual else 2.0), 2)

    return {
        "meta": {
            "usuario": perfil.get("nombre_usuario", "Usuario"),
            "moneda": moneda,
            "simbolo": simbolo,
            "frecuencia_pago": "mensual" if es_mensual else "quincenal",
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
            "presupuesto_semanal_libres": presupuesto_semanal_libres,
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


def evaluar_compra(
    perfil: dict[str, Any],
    monto_compra: float,
    nombre_compra: str,
    fecha_actual: dt.date,
    categoria_compra: str = "auto",
) -> dict[str, Any]:
    simbolo = perfil.get("simbolo_moneda", "$")
    ingreso_ref = float(perfil.get("ingreso_referencia_quincenal", 2300.0))
    categoria = detectar_categoria_compra(nombre_compra, categoria_compra)

    plan_ref = planificar_quincena(perfil, ingreso_ref, fecha_actual)
    es_mensual = plan_ref["meta"].get("frecuencia_pago") == "mensual"
    pagos_por_mes = 1.0 if es_mensual else 2.0
    ahorro_por_pago_tipico = max(0.0, plan_ref["resumen_montos"]["ahorro_fuerte_total"])
    ahorro_mensual_tipico = round(ahorro_por_pago_tipico * pagos_por_mes, 2)
    ahorro_quincenal_tipico = ahorro_por_pago_tipico

    cuota_quincenal_segura = round(ahorro_por_pago_tipico * 0.40, 2)

    tarjetas = perfil.get("tarjetas_credito", [])
    info_tc: dict[str, Any] | None = None
    dia_corte = 6
    dia_limite = 1
    if tarjetas:
        tc = tarjetas[0]
        dia_corte = int(tc.get("dia_corte", 6))
        dia_limite = int(tc.get("dia_limite_pago", 1))
        limite = float(tc.get("limite_credito", 10000.0))
        tope_30 = round(limite * 0.30, 2)

        gastos_tc_mes = sum(
            float(g["monto"])
            for g in perfil.get("gastos_fijos", [])
            if str(g.get("metodo", "")).lower() == "tc"
        )
        saldo_previo = float(tc.get("saldo_al_corte_pendiente", 0.0)) + float(
            tc.get("cuotas_fijas_mes", 0.0)
        )
        margen_30_disponible = round(max(0.0, tope_30 - gastos_tc_mes - saldo_previo), 2)

        ciclo_hoy = calcular_ciclo_tc_para_fecha(fecha_actual, dia_corte, dia_limite)
        proximo_corte = dt.date.fromisoformat(ciclo_hoy["fecha_corte"])
        fecha_oro = proximo_corte + dt.timedelta(days=1)
        ciclo_oro = calcular_ciclo_tc_para_fecha(fecha_oro, dia_corte, dia_limite)

        dias_espera_oro = (fecha_oro - fecha_actual).days
        conviene_esperar_corte = (
            dias_espera_oro <= 15
            and ciclo_oro["dias_financiamiento_gratis"]
            > ciclo_hoy["dias_financiamiento_gratis"] + 10
        )

        info_tc = {
            "tarjeta": tc.get("nombre", "TC"),
            "limite_credito": limite,
            "tope_saludable_30_pct": tope_30,
            "margen_30_pct_disponible": margen_30_disponible,
            "respeta_regla_30_pct": monto_compra <= margen_30_disponible,
            "si_compras_hoy": ciclo_hoy,
            "ventana_oro_recomendada": ciclo_oro,
            "dias_espera_para_ventana_oro": dias_espera_oro,
            "conviene_esperar_ventana_oro": conviene_esperar_corte,
        }

    temporadas_gt = analizar_temporadas_festivas_gt(
        fecha_actual=fecha_actual,
        categoria=categoria,
        dia_corte=dia_corte,
        dia_limite_pago=dia_limite,
    )

    deudas_temporales = [
        g
        for g in perfil.get("gastos_fijos", [])
        if g.get("categoria") == "deuda_temporal" or "cuota" in g.get("nombre", "").lower()
    ]

    quincenas_para_contado = (
        round(monto_compra / max(1.0, ahorro_quincenal_tipico * 0.70), 1)
        if ahorro_quincenal_tipico > 0
        else 99.0
    )

    opciones_cuotas = []
    for n_meses in (3, 6, 12):
        cuota_mes = round(monto_compra / n_meses, 2)
        cuota_q = round(cuota_mes / pagos_por_mes, 2)
        holgado = cuota_q <= max(cuota_quincenal_segura, ahorro_por_pago_tipico * 0.50)
        opciones_cuotas.append(
            {
                "plazo_meses": n_meses,
                "cuota_mensual_0_interes": cuota_mes,
                "apartado_por_quincena": cuota_q,
                "viable_sin_apreton": holgado,
            }
        )

    if monto_compra <= ahorro_quincenal_tipico * 0.75:
        semaforo = "VERDE (Compra de Contado / 1 Pago al Corte)"
        estrategia = (
            "Puedes pagarlo al 100% en 1 solo pago al corte sin tocar tu ahorro base ni tu piso de salidas. "
            "Apártalo de tu excedente de esta quincena."
        )
    elif monto_compra <= ahorro_mensual_tipico * 1.1:
        semaforo = "VERDE-AMARILLO (Contado en Ventana de Oro o 3 Cuotas 0%)"
        apartado_3q = round(monto_compra / 3.0, 2)
        estrategia = (
            f"Cómpralo en la Ventana de Oro de tu TC para ganar ~50 días y júntalo en 2-3 quincenas "
            f"({simbolo}{apartado_3q:,.2f}/quincena), o pide 3 cuotas sin intereses."
        )
    elif opciones_cuotas[1]["viable_sin_apreton"]:
        semaforo = "AMARILLO (Usar 6 Cuotas 0% Interés o Ahorro Programado)"
        c6 = opciones_cuotas[1]
        estrategia = (
            f"De contado te apretaría, pero en 6 cuotas SIN intereses (0%) solo apartas "
            f"{simbolo}{c6['apartado_por_quincena']:,.2f}/quincena ({simbolo}{c6['cuota_mensual_0_interes']:,.2f}/mes) "
            "y sigues ahorrando para tus metas principales."
        )
    else:
        semaforo = "ROJO (Posponer o Ahorrar Previamente)"
        estrategia = (
            f"Excede tu margen cómodo actual. Recomendación: ahorrar {simbolo}{cuota_quincenal_segura:,.2f}/quincena "
            "o esperar a que se liberen compromisos actuales."
        )
        if deudas_temporales:
            nombres_dt = ", ".join(d["nombre"] for d in deudas_temporales)
            estrategia += f" Nota: cuando termines [{nombres_dt}] liberarás flujo extra para comprarlo sin presión."

    return {
        "compra": {
            "nombre": nombre_compra or "Compra evaluada",
            "categoria": categoria,
            "monto": round(monto_compra, 2),
            "simbolo": simbolo,
            "fecha_evaluacion": fecha_actual.isoformat(),
        },
        "capacidad_usuario": {
            "ingreso_quincenal_referencia": ingreso_ref,
            "ahorro_libre_quincenal": ahorro_quincenal_tipico,
            "cuota_quincenal_comoda_maxima": round(ahorro_quincenal_tipico * 0.50, 2),
            "quincenas_necesarias_de_contado": quincenas_para_contado,
        },
        "semaforo": semaforo,
        "estrategia_recomendada": estrategia,
        "calendario_optimo_tc": info_tc,
        "temporadas_festivas_guatemala": temporadas_gt,
        "simulacion_cuotas_0_interes": opciones_cuotas,
    }


def renderizar_evaluacion_compra_md(ev: dict[str, Any]) -> str:
    c = ev["compra"]
    cap = ev["capacidad_usuario"]
    s = c["simbolo"]
    tc = ev.get("calendario_optimo_tc")
    gt = ev.get("temporadas_festivas_guatemala")

    lines = [
        f"# Asesor de Compras Arceus — {c['nombre']} ({s}{c['monto']:,.2f}) [{c['categoria'].upper()}]",
        "",
        f"- **Veredicto Financiero:** **{ev['semaforo']}**",
        f"- **Estrategia de Flujo:** {ev['estrategia_recomendada']}",
        f"- **Tu margen libre por quincena:** `{s}{cap['ahorro_libre_quincenal']:,.2f}` (cuota cómoda máx: `{s}{cap['cuota_quincenal_comoda_maxima']:,.2f}/quincena`)",
        "",
    ]

    if gt:
        lines.extend(
            [
                "## 1. Calendario de Temporadas y Fechas Festivas (Guatemala)",
                "",
                f"> 💡 **{gt['estrategia_temporada_gt']}**",
                "",
                "| Temporada en Guatemala | Fechas Clave | Descuento Típico GT | Impacto en tu TC | Recomendación Arceus |",
                "| :--- | :--- | :--- | :--- | :--- |",
            ]
        )
        for v in gt["comparativa_fechas_festivas"]:
            lines.append(
                f"| **{v['temporada']}** | `{v['fechas']}` | {v['descuento_tipico_gt']} | {v['impacto_tc']} | {v['veredicto']} |"
            )
        lines.append("")

    if tc:
        hoy = tc["si_compras_hoy"]
        oro = tc["ventana_oro_recomendada"]
        marca_hoy = "✅ Óptimo hoy" if not tc["conviene_esperar_ventana_oro"] else "⚠️ Corto plazo"
        marca_oro = "⭐ MEJOR FECHA TC (Ventana de Oro)"
        lines.extend(
            [
                f"## 2. Ciclo Exacto de tu Tarjeta ({tc['tarjeta']})",
                "",
                "| Escenario | Fecha compra | Fecha corte | Fecha límite pago (0%) | Días gratis | Evaluación |",
                "| :--- | :--- | :--- | :--- | ---: | :--- |",
                f"| **Comprar HOY** | `{hoy['fecha_compra']}` | `{hoy['fecha_corte']}` | **`{hoy['fecha_limite_pago']}`** | `{hoy['dias_financiamiento_gratis']} días` | {marca_hoy} |",
                f"| **Esperar post-corte** | **`{oro['fecha_compra']}`** | `{oro['fecha_corte']}` | **`{oro['fecha_limite_pago']}`** | **`{oro['dias_financiamiento_gratis']} días`** | {marca_oro} |",
                "",
                f"- **Impacto en Buró (Regla <30%):** Margen disponible bajo el 30%: `{s}{tc['margen_30_pct_disponible']:,.2f}` → "
                + ("✅ Respeta el <30%." if tc["respeta_regla_30_pct"] else "⚠️ Supera el 30%; abona antes del corte o usa cuotas."),
                "",
            ]
        )

    lines.extend(
        [
            "## 3. Simulación en Cuotas SIN Intereses (0%)",
            "",
            "| Plazo | Cuota Mensual | Apartado por Quincena | ¿Te deja tranquilo sin apretón? |",
            "| :--- | ---: | ---: | :--- |",
        ]
    )
    for op in ev["simulacion_cuotas_0_interes"]:
        estado = "✅ Sí (Cómodo)" if op["viable_sin_apreton"] else "⚠️ Ajustado"
        lines.append(
            f"| **{op['plazo_meses']} meses** | `{s}{op['cuota_mensual_0_interes']:,.2f}/mes` | "
            f"**`{s}{op['apartado_por_quincena']:,.2f}/quincena`** | {estado} |"
        )

    return "\n".join(lines)


def renderizar_markdown(plan: dict[str, Any], compact: bool = False) -> str:
    m = plan["meta"]
    r = plan["resumen_montos"]
    a = plan["acciones_dia_pago"]
    s = m["simbolo"]
    es_mensual = m.get("frecuencia_pago") == "mensual"
    titulo_plan = "Plan Mensual Arceus" if es_mensual else "Plan Quincenal Arceus"

    lines: list[str] = [
        f"# {titulo_plan} — {m['codigo_periodo']} ({m['fecha_pago']} → {m['proximo_pago']})",
        f"**Ingreso:** `{s}{r['ingreso_quincena']:,.2f}` | **Ahorro Fuerte:** `{s}{r['ahorro_fuerte_total']:,.2f}` (`{r['porcentaje_ahorro_real']}%`) | **Libre (Salidas):** `{s}{r['gastos_libres_salidas']:,.2f}` (`{s}{r['presupuesto_semanal_libres']:,.2f}/semana`)",
        "",
    ]

    if plan.get("alerta_liquidez"):
        lines.extend([f"> ⚠️ **{plan['alerta_liquidez']}**", ""])

    lines.extend(
        [
            "## 1. Cubetas de Acción (Hoy)",
            "| Cubeta | Monto | Detalle |",
            "| :--- | ---: | :--- |",
            f"| **Ahorro Fuerte** | **{s}{a['mover_a_cuenta_ahorro_fuerte']:,.2f}** | Págate a ti primero |",
            f"| **Retirar Efectivo** | **{s}{a['retirar_efectivo_cajero']:,.2f}** | 1 visita al cajero |",
            f"| **Transferencias** | **{s}{a['transferir_hoy_o_en_fecha']:,.2f}** | Pagos por transferencia |",
            f"| **Dejar en Débito** | **{s}{a['dejar_en_cuenta_debito_total']:,.2f}** | Débito fijo `{s}{a['detalle_en_debito']['cargos_debito_fijos']:,.2f}` + Apartado TC `{s}{a['detalle_en_debito']['apartado_intocable_tc']:,.2f}` + Anti-Apretón 50% `{s}{a['detalle_en_debito']['apartado_prorrateo_proxima_quincena']:,.2f}` + Libre `{s}{a['detalle_en_debito']['disponible_gastos_libres_y_salidas']:,.2f}` |",
            "",
        ]
    )

    if plan["calendario_pagos_quincena"]:
        lines.extend(
            [
                "## 2. Calendario de Pagos (Esta Quincena)",
                "| Fecha | Gasto | Método | Recibo | Sale hoy | Nota |",
                "| :--- | :--- | :--- | ---: | ---: | :--- |",
            ]
        )
        for p in plan["calendario_pagos_quincena"]:
            lines.append(
                f"| `{p['fecha_vencimiento']}` | {p['nombre']} | `{p['metodo'].upper()}` | "
                f"{s}{p['monto_total_recibo']:,.2f} | **{s}{p['monto_de_este_ingreso']:,.2f}** | {p['nota']} |"
            )
        lines.append("")

    if plan["apartados_prorrateo"]:
        lines.extend(
            [
                "## 3. Blindaje Anti-Apretón (50% Próxima Quincena)",
                "| Vence | Gasto fuerte | Recibo | Apartar HOY (50%) |",
                "| :--- | :--- | ---: | ---: |",
            ]
        )
        for ap in plan["apartados_prorrateo"]:
            lines.append(
                f"| `{ap['fecha_vencimiento']}` | {ap['nombre']} | {s}{ap['monto_total_recibo']:,.2f} | **{s}{ap['monto_apartar_hoy']:,.2f}** |"
            )
        lines.append("")

    if plan["desglose_ahorro"] and not compact:
        lines.extend(
            [
                "## 4. Metas de Ahorro",
                "| Meta | % | Monto |",
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
                f"## 5. Tarjeta de Crédito ({tc['nombre']})",
                f"- **Corte:** `{tc['proximo_corte']}` ({tc['dias_para_corte']}d) | **Límite pago:** `{tc['proximo_limite_pago']}` ({tc['dias_para_limite_pago']}d) | **Mejor fecha para comprar:** `{tc['ventana_oro_compras']}` (~{tc['dias_financiamiento_ventana_oro']}d sin interés)",
                f"- **Cargos TC quincena:** `{s}{tc['cargos_tc_quincena']:,.2f}` | **Apartado Totalero en Débito:** **`{s}{tc['apartado_total_tc_en_debito']:,.2f}`** | **Uso:** `{tc['porcentaje_uso_estimado']}%`",
            ]
        )
        for c in tc["consejos"]:
            lines.append(f"- {c}")
        lines.append("")

    return "\n".join(lines)


def guardar_reporte_e_historial(plan: dict[str, Any], markdown_text: str) -> dict[str, str]:
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
        description="Motor determinista de planificación financiera y asesor de compras Arceus."
    )
    parser.add_argument("--check-setup", action="store_true", help="Verifica estado del perfil.")
    parser.add_argument("--perfil", type=Path, default=DEFAULT_PROFILE_PATH)
    parser.add_argument("--usar-ejemplo", action="store_true")
    parser.add_argument("--ingreso", type=float, help="Monto recibido en la quincena.")
    parser.add_argument("--evaluar-compra", type=float, help="Monto de una compra a evaluar.")
    parser.add_argument("--nombre-compra", type=str, default="Compra deseada")
    parser.add_argument(
        "--categoria-compra",
        type=str,
        default="auto",
        choices=["auto", "ropa", "tecnologia", "regalos", "general"],
        help="Categoría para evaluar temporadas festivas en Guatemala.",
    )
    parser.add_argument("--fecha", type=str, default=dt.date.today().isoformat())
    parser.add_argument("--gasto-extra", type=float, default=0.0)
    parser.add_argument("--nota-extra", type=str, default="")
    parser.add_argument("--sin-prorrateo-previo", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--guardar", action="store_true")

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
                            "modo": "OPERATIVO",
                            "usuario": data.get("nombre_usuario"),
                            "moneda": data.get("moneda"),
                            "gastos": len(data.get("gastos_fijos", [])),
                            "tc": len(data.get("tarjetas_credito", [])),
                        },
                        ensure_ascii=False,
                    )
                )
                return 0
            except Exception as exc:
                print(json.dumps({"configurado": False, "modo": "ENTREVISTA_INICIAL", "error": str(exc)}))
                return 1
        print(json.dumps({"configurado": False, "modo": "ENTREVISTA_INICIAL"}))
        return 0

    if not perfil_path.exists():
        print(
            json.dumps({"error": "PERFIL_NO_CONFIGURADO", "modo_requerido": "ENTREVISTA_INICIAL"}),
            file=sys.stderr,
        )
        return 2

    fecha_ref = dt.date.fromisoformat(args.fecha)
    perfil = json.loads(perfil_path.read_text(encoding="utf-8"))

    if args.evaluar_compra is not None:
        if args.evaluar_compra <= 0:
            parser.error("--evaluar-compra requiere un monto mayor a 0.")
        ev = evaluar_compra(
            perfil,
            args.evaluar_compra,
            args.nombre_compra,
            fecha_ref,
            args.categoria_compra,
        )
        if args.json:
            print(json.dumps(ev, ensure_ascii=False, indent=2))
        else:
            print(renderizar_evaluacion_compra_md(ev))
        return 0

    if args.ingreso is None or args.ingreso <= 0:
        parser.error("Indica --ingreso <MONTO> o --evaluar-compra <MONTO>.")

    plan = planificar_quincena(
        perfil=perfil,
        ingreso=args.ingreso,
        fecha_pago=fecha_ref,
        gasto_extra=args.gasto_extra,
        nota_extra=args.nota_extra,
        usar_prorrateo_previo=not args.sin_prorrateo_previo,
    )
    md = renderizar_markdown(plan, compact=args.compact)

    if args.guardar and not args.usar_ejemplo:
        plan["archivos_generados"] = guardar_reporte_e_historial(plan, md)

    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(md)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
