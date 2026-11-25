# Arceus Finanzas (`arceus-finanzas`)

**Arceus** es un asistente y planificador financiero quincenal basado en **Agent Skills + un motor determinista en Python**. Está diseñado para personas que reciben un ingreso distinto cada quincena (o cada mes) y quieren saber **qué pagar, en qué fecha, con qué método de pago (`efectivo`, `transferencia`, `débito`, `tarjeta de crédito`)**, cómo **nunca sentirse apretadas** en una quincena pesada y cómo mantener un **ahorro fuerte** constante.

---

## ¿Qué problema resuelve?

Cuando organizas tu quincena en un chat de IA normal, suelen ocurrir tres problemas:

1. **Pérdida de memoria:** Cada quincena tienes que volver a explicarle tus gastos fijos, tus fechas de pago y cómo usas tus tarjetas.
2. **Alucinaciones de fechas y sumas:** Los modelos de lenguaje adivinan calendarios y a veces suman mal o colocan pagos en la quincena equivocada.
3. **Quincenas desbalanceadas ("apretón"):** Si tu renta o pagos más fuertes caen todos a inicios de mes, una quincena te deja sin liquidez y la otra te sobra.

**Cómo lo resuelve `arceus-finanzas`:**
- **Entrevista inicial automática (`/setup`):** La primera vez que cualquier persona abre el proyecto y habla con Arceus, el agente detecta que no existe `perfil/usuario.json` y realiza una entrevista guiada en 4 bloques cortos para entender su situación financiera.
- **Memoria persistente y 100% privada:** Tu perfil se guarda localmente en `perfil/usuario.json` (ignorado por `.gitignore`, por lo que **nunca se sube a GitHub**). En las siguientes quincenas solo dices *"Hoy me pagaron 4,850"* y Arceus recuerda todo.
- **Motor determinista en Python (`tools/arceus_engine.py`):** La IA no suma a ojo ni adivina el calendario. Ejecuta un script que calcula fechas reales, cuadra el ingreso al centavo y separa tu dinero en cubetas accionables.
- **Blindaje Anti-Apretón (Prorrateo 50/50):** Si en la próxima quincena vence un gasto fuerte (ej. renta), Arceus aparta automáticamente el **50% desde esta quincena** y garantiza tu **piso de gastos libres/salidas** antes de calcular el ahorro excedente.
- **Coach para tu 1ra Tarjeta de Crédito (`arceus-tc`):** Calcula tu próxima **fecha de corte** y **fecha límite de pago**, te dice si estás en buena ventana para comprar (~45 días sin intereses), cuida que no pases del **30% de utilización** y congela en tu cuenta de débito el **Apartado Intocable TC** para que siempre seas *totalero* (0% intereses).

---

## Cómo empezar (Para cualquier usuario)

### Requisitos
- **Python 3.10+** (no requiere librerías externas; usa únicamente la biblioteca estándar de Python).
- Un entorno de agente compatible con Skills o `AGENTS.md` / `CLAUDE.md` (**Google Antigravity**, **Claude Code**, **Cursor**, **Codex**, etc.).

### 1. Clonar el repositorio

```bash
git clone https://github.com/akthaly/arceus-finanzas.git
cd arceus-finanzas
```

### 2. Hablar con Arceus por primera vez (Entrevista Inicial)

Abre la carpeta `arceus-finanzas` en tu agente de IA y escribe:

> *"Hola Arceus, quiero empezar a organizar mis finanzas"* (o ejecuta `/setup`)

Arceus detectará automáticamente que eres un usuario nuevo y te hará preguntas en **4 pasos sencillos**:
1. **Moneda e ingresos** (qué días te pagan y si tu ingreso es variable).
2. **Gastos fijos, día de pago y método** (`efectivo`, `transferencia`, `debito`, `tc`).
3. **Tu Tarjeta de Crédito** (fecha de corte, fecha límite de pago y límite de crédito, con guía paso a paso si es tu primera tarjeta).
4. **Tu piso de tranquilidad y ahorro fuerte** (cuánto necesitas libre para salidas sin sentirte apretado y tus metas de ahorro).

### 3. Planificar cada quincena

Una vez creado tu perfil, cada día de pago solo escribe:

> *"Arceus, hoy me depositaron 4,850"* (o `/quincena 4850`)

Arceus generará tu tabla completa en pantalla, guardará el reporte en `reportes/` y actualizará tu progreso en `historial/quincenas.csv`.

---

## Estructura del Repositorio

```text
arceus-finanzas/
├── AGENTS.md                          # Instrucciones universales para agentes (Antigravity, Codex, Cursor)
├── CLAUDE.md                          # Puntero de configuración para Claude Code
├── perfil/
│   ├── usuario.example.json           # Plantilla de ejemplo (pública)
│   └── usuario.json                   # Tu perfil real generado por Arceus (IGNORADO por Git)
├── historial/
│   ├── quincenas.example.csv          # Ejemplo de historial quincenal
│   └── quincenas.csv                  # Tu historial real de ingresos y ahorro (IGNORADO por Git)
├── reportes/
│   ├── reporte-ejemplo.md             # Ejemplo de cómo se ve una tabla quincenal de Arceus
│   └── YYYY-MM-QX_YYYY-MM-DD.md       # Tus planes quincenales guardados (IGNORADOS por Git)
├── tools/
│   ├── arceus_engine.py               # Motor determinista de fechas, prorrateo, cubetas y TC
│   └── test_arceus_engine.py          # Tests unitarios del motor
├── .agents/
│   └── skills/
│       ├── arceus/
│       │   └── SKILL.md               # Skill principal (entrevista inicial + plan quincenal)
│       └── arceus-tc/
│           └── SKILL.md               # Skill asesor de primera tarjeta de crédito
└── .claude/
    └── commands/
        ├── setup.md                   # Comando /setup
        └── quincena.md                # Comando /quincena
```

---

## Probar el motor directamente desde la terminal

Puedes ver una demostración inmediata con el perfil de ejemplo incluido:

```bash
# Ver estado de configuración del usuario
python tools/arceus_engine.py --check-setup

# Simular una quincena de 4,850 con el perfil de ejemplo (modo compacto para ahorrar tokens)
python tools/arceus_engine.py --usar-ejemplo --ingreso 4850 --fecha 2026-11-15 --compact

# Evaluar si conviene hacer una compra y cuál es la mejor fecha exacta del calendario
python tools/arceus_engine.py --usar-ejemplo --evaluar-compra 1200 --nombre-compra "Ropa Fin de Año" --fecha 2026-12-05

# Ejecutar los tests unitarios
python -m unittest discover -s tools -p "test_*.py"
```

---

## Privacidad y Seguridad

`arceus-finanzas` está diseñado desde cero para poder compartirse públicamente en GitHub sin exponer datos personales:
- `.gitignore` bloquea automáticamente `perfil/usuario.json`, `historial/*.csv` y `reportes/*.md`.
- El motor corre 100% en local sin conectarse a APIs externas ni bancos.
