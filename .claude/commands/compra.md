# /compra — Evaluar una Compra y Mejor Fecha para Comprar

Sigue la **Fase C** de [`.agents/skills/arceus/SKILL.md`](../../.agents/skills/arceus/SKILL.md):

1. Si el usuario dio el monto y artículo en `$ARGUMENTS` (ej. `/compra 1200 Ropa`), ejecuta directamente:
   `python tools/arceus_engine.py --evaluar-compra <MONTO> --nombre-compra "<ARTICULO>"`
2. Presenta la tabla del motor (Semáforo, Comprar HOY vs. Ventana de Oro post-corte, impacto <30% en TC y simulación de 3/6/12 cuotas 0% interés) con máximo 3 recomendaciones breves.
