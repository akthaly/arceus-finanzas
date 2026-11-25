---
name: arceus-tc
description: >
  Asesor compacto de Primera Tarjeta de Crédito y fechas óptimas de compra (Arceus TC).
  Úsalo cuando el usuario pregunte sobre fecha de corte, fecha de pago, intereses, cuotas 0%
  o cómo usar su primera tarjeta de crédito.
---

# Arceus TC — Reglas Rápidas de Primera Tarjeta de Crédito (Token-Lean)

Para evaluar cualquier compra o fecha óptima con la TC del usuario, **no calcules a mano**: ejecuta `python tools/arceus_engine.py --evaluar-compra <MONTO> --nombre-compra "<ITEM>"`.

## 4 Reglas Clave para Recomendar
1. **Apartado Totalero (0% interés):** Todo cargo con TC congela ese mismo monto en la cuenta de débito (`Apartado Intocable TC`). Siempre se paga el *"Pago de contado / Para no generar intereses"* 2 días antes de `dia_limite_pago`. Jamás el pago mínimo.
2. **Ventana de Oro para Comprar (~45-55 días gratis):**
   - **Mejor fecha:** `dia_corte + 1` (entra hasta el corte del mes siguiente).
   - **Peor fecha:** 1 a 4 días antes de `dia_corte` (cierra de inmediato y toca pagarlo en ~20-25 días).
3. **Regla del <30% (Récord crediticio):** Mantener el saldo al día de corte `<= 30%` de `limite_credito`. Si se supera, abonar antes del `dia_corte`.
4. **Cuotas:** Solo usar cuotas si son **0% interés** (ej. NeoCuotas / Meses sin intereses) y la cuota quincenal no supera el `40%-50%` del ahorro libre quincenal del usuario.
