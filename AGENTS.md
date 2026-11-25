# Agent Guidelines — Arceus Finanzas (`arceus-finanzas`)

Asistente financiero quincenal y asesor de compras diseñado para **mínimo consumo de tokens** y **cero alucinaciones matemáticas**.

## Fuente Única de Verdad
- **Skill Principal:** [`.agents/skills/arceus/SKILL.md`](.agents/skills/arceus/SKILL.md)
- **Skill Tarjeta de Crédito:** [`.agents/skills/arceus-tc/SKILL.md`](.agents/skills/arceus-tc/SKILL.md)
- **Motor Determinista:** [`tools/arceus_engine.py`](tools/arceus_engine.py)

## Reglas de Ahorro de Tokens y Privacidad
1. **Un solo comando por consulta:**
   - Estado: `python tools/arceus_engine.py --check-setup`
   - Planificar quincena: `python tools/arceus_engine.py --ingreso <MONTO> --compact --guardar`
   - Evaluar compra y fecha óptima: `python tools/arceus_engine.py --evaluar-compra <MONTO> --nombre-compra "<ITEM>"`
2. **No leas `perfil/usuario.json` innecesariamente:** El script ya lo lee. Solo ábrelo si debes crearlo (Entrevista Inicial) o editarlo.
3. **Respuestas cortas:** Imprime la tabla del motor y máximo 3 bullets accionables.
4. **Privacidad:** Nunca rastrees en Git `perfil/usuario.json`, `historial/*.csv` ni `reportes/*.md`, y jamás almacenes DPI, números de tarjeta ni nombres legales completos.
