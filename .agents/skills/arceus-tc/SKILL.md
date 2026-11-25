---
name: arceus-tc
description: >
  Guía y asesor especializado en Primera Tarjeta de Crédito de Arceus. Explica y calcula
  estrategias para usar una tarjeta de crédito por primera vez sin pagar intereses (ser totalero),
  optimizar compras según la fecha de corte y fecha límite de pago, cuidar el porcentaje de
  utilización (<30%) y decidir qué gastos pasar de débito/efectivo a TC.
---

# Arceus TC — Asesor de Primera Tarjeta de Crédito

Usa este skill cuando el usuario tenga dudas sobre su **primera tarjeta de crédito**, quiera saber **cuándo comprar con la tarjeta**, cómo funcionan la **fecha de corte** y la **fecha límite de pago**, o qué gastos fijos le conviene pasar a su tarjeta de crédito.

---

## Los 4 Principios Innegociables de Arceus para tu 1ra Tarjeta de Crédito

1. **La Tarjeta de Crédito NO es una extensión de tu sueldo, es un método de pago:**
   - En el sistema Arceus, cada vez que pagas un gasto con tu TC (por ejemplo, el Internet o una salida), **ese mismo monto se congela inmediatamente en tu cuenta de débito** bajo el nombre de `Apartado Intocable TC`.
   - Así, cuando llega la fecha de pago de la tarjeta, el dinero **ya está esperando en tu cuenta de débito**. Pagas el 100%, generas historial crediticio perfecto y pagas **0.00 de intereses**.

2. **Fecha de Corte vs. Fecha Límite de Pago (El Reloj de los 45 Días):**
   - **Día de Corte (ej. día 8):** Es el día en que el banco "toma la foto" de todo lo que compraste en los últimos 30 días y cierra la factura.
   - **Día Límite de Pago (ej. día 28):** Es la fecha máxima (usualmente ~20 días después del corte) para pagar esa "foto" sin que te cobren intereses.
   - **El truco de Arceus:**
     - **Mejor día para comprar:** El día **después** de tu fecha de corte (ej. día 9). Esa compra entrará hasta la foto del mes siguiente y tendrás casi **45 a 50 días** para pagarla sin intereses.
     - **Peor día para comprar algo grande:** 1 a 3 días **antes** de tu fecha de corte (ej. días 5 al 8). Entra en la foto que cierra de inmediato y tendrás que pagarla en apenas ~20 días.

3. **La Regla del Totalero (Qué botón presionar al pagar la tarjeta):**
   - En el estado de cuenta siempre aparecen tres montos:
     1. *Pago Mínimo:* **TRAMPA.** Si pagas solo esto, el banco te cobra intereses altísimos (40% a 80% anual) sobre todo tu saldo.
     2. *Pago para no generar intereses / Pago de contado al corte:* **ESTE ES EL QUE SIEMPRE DEBES PAGAR.**
     3. *Saldo total a la fecha:* Incluye lo del corte más lo que compraste después del corte.
   - Paga siempre el **Pago de contado / Para no generar intereses** al menos **2 días hábiles antes** de la fecha límite de pago (por si el banco tarda en procesar o cae en fin de semana).

4. **La Regla del 30% (Cómo subir tu récord crediticio rápido):**
   - Los burós de crédito premian a quienes usan su tarjeta pero **no parecen depender de ella**.
   - Si tu límite es de `6,000`, procura que el día de tu **fecha de corte** el saldo acumulado no pase del **30%** (`1,800`).
   - Si en un mes usaste más del 30%, simplemente haz un pago parcial desde tu apartado de débito **2 días antes de la fecha de corte** para que "la foto" salga limpia y por debajo del 30%.

---

## Cómo asesorar al usuario con sus datos reales

1. Lee `perfil/usuario.json` (si existe) para ver su `dia_corte`, `dia_limite_pago`, `limite_credito` y qué gastos de `gastos_fijos` tienen `"metodo": "tc"`.
2. Revisa cuáles de sus gastos fijos actuales están en `debito` o `efectivo` pero son servicios recurrentes predecibles (internet, teléfono, luz, streaming, gimnasio) y sugiérele cuáles podría pagar con su TC para construir historial en piloto automático sin gastar un centavo extra.
3. Recuérdale cuántos días faltan para su próximo corte y su próxima fecha límite de pago ejecutando `python tools/arceus_engine.py --check-setup` o consultando el último reporte en `reportes/`.
