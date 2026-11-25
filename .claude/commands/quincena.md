# /quincena — Planificar un Nuevo Pago Quincenal con Arceus

Lee y sigue las instrucciones de `.agents/skills/arceus/SKILL.md`.

1. Ejecuta primero `python tools/arceus_engine.py --check-setup`.
   - Si `"configurado": false`, inicia primero la **Fase A: Entrevista Inicial**.
2. Si `"configurado": true`, sigue la **Fase B: Planificación de Quincena**:
   - Si el usuario pasó el monto en `$ARGUMENTS` (ej. `/quincena 4850`), úsalo y confirma si tiene algún gasto extra puntual antes de guardar, o corre directamente `python tools/arceus_engine.py --ingreso <MONTO> --guardar`.
   - Presenta la tabla de acciones inmediatas por método de pago (`efectivo`, `transferencia`, `debito`, `tc`), el calendario de vencimientos, el blindaje anti-apretón (50% próxima quincena), la distribución de ahorro fuerte y la estrategia de su tarjeta de crédito.
