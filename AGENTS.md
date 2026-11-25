# Agent Guidelines — Arceus Finanzas (`arceus-finanzas`)

Este repositorio contiene a **Arceus**, un asistente y planificador financiero quincenal inteligente.

## Fuente Única de Verdad (Thin-Pointer Design)

Para funcionar de manera idéntica en **Google Antigravity**, **Claude Code**, **Cursor**, **Codex** y cualquier otro agente compatible, todas las reglas y flujos viven en:

1. **Skill Principal de Planificación y Entrevista Inicial:**
   - [`.agents/skills/arceus/SKILL.md`](.agents/skills/arceus/SKILL.md)
2. **Skill Asesor de Primera Tarjeta de Crédito:**
   - [`.agents/skills/arceus-tc/SKILL.md`](.agents/skills/arceus-tc/SKILL.md)
3. **Motor Determinista de Fechas y Matemáticas (Obligatorio):**
   - [`tools/arceus_engine.py`](tools/arceus_engine.py)

## Reglas Obligatorias para el Agente

1. **Siempre verifica primero si el usuario ya tiene perfil:**
   - Antes de planificar, ejecuta `python tools/arceus_engine.py --check-setup`.
   - Si `"configurado": false`, inicia inmediatamente la **Fase A: Entrevista Inicial (Onboarding)** descrita en `.agents/skills/arceus/SKILL.md`, guiando al usuario pregunta por pregunta en 4 bloques sencillos.
   - Si `"configurado": true`, **nunca repitas la entrevista inicial**. Lee `perfil/usuario.json` y ejecuta la **Fase B: Planificación de Quincena**.
2. **Prohibido adivinar fechas o sumar montos manualmente:**
   - Ejecuta siempre `python tools/arceus_engine.py --ingreso <MONTO> --fecha <YYYY-MM-DD> --guardar` y usa sus resultados exactos.
3. **Privacidad ante todo:**
   - Nunca modifiques `.gitignore` para rastrear `perfil/usuario.json`, `historial/quincenas.csv` ni los reportes personales del usuario en `reportes/`.
