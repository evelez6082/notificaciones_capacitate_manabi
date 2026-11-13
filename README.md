# Notificador unificado — Capacítate Manabí

Un único programa para enviar **campañas de notificación** a estudiantes:
correo por **Amazon SES** y WhatsApp por la **API de Meta Cloud**.

Todo se configura en [`config.json`](config.json); los listados van en
[`listados/`](listados/), el historial acumulado en
[`historial/historial.csv`](historial/historial.csv) y los informes se guardan
en [`informes/`](informes/) con la fecha.

## Estructura

```
notificaciones/
├── notificador.py          ← programa principal (un solo archivo)
├── config.json             ← campañas y valores por defecto
├── requirements.txt
├── .env                     ← credenciales (NO subir a git)
├── .env.example
├── assets/                  ← imágenes embebidas en el correo
├── templates/               ← plantillas HTML + texto (bienvenida, recordatorio, ...)
├── listados/                ← Excel/CSV de entrada (nuevos listados se agregan aquí)
├── historial/historial.csv  ← historial acumulado de todos los envíos
└── informes/                ← informe generado por cada envío (con fecha)
```

## Instalación

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Copia `.env.example` a `.env` y completa las credenciales:

```env
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
META_WA_ACCESS_TOKEN=...
META_WA_PHONE_NUMBER_ID=...
```

## Uso

### 1. Probar (1 correo + 1 WhatsApp de prueba)

```bash
python3 notificador.py test --campaign bienvenida
```

### 2. Enviar una campaña real

```bash
# Simulación (no envía nada):
python3 notificador.py live --campaign bienvenida --dry-run

# Envío real:
python3 notificador.py live --campaign bienvenida --yes
```

### 3. Enviar a un listado nuevo

Deja el archivo en `listados/` y pásalo con `--excel`:

```bash
python3 notificador.py live --campaign bienvenida --excel listados/nuevos_estudiantes.xlsx --yes
```

### 4. Ver historial acumulado

```bash
python3 notificador.py historial
```

### 5. Generar un informe desde el historial

```bash
python3 notificador.py informe --campaign bienvenida
python3 notificador.py informe --campaign bienvenida --fecha 2026-10-08
```

## Comandos y opciones

| Comando      | Qué hace |
|--------------|----------|
| `test`       | Envía 1 correo y 1 WhatsApp de prueba |
| `live`       | Envío real al listado (genera informe) |
| `informe`    | Genera informe desde el historial |
| `historial`  | Resumen del historial acumulado |

Opciones de `live`:

| Opción | Descripción |
|--------|-------------|
| `--excel RUTA` | Listado a usar (Excel o CSV) |
| `--hoja NOMBRE` | Hoja del Excel (por defecto la activa) |
| `--canal email` / `whatsapp` | Enviar solo por un canal |
| `--credenciales RUTA` | Completar usuario/contraseña desde otro listado |
| `--dry-run` | Simular sin enviar |
| `--yes` | No pedir confirmación |
| `--limit N` / `--start-index N` | Procesar un subconjunto |
| `--subject "..."` | Sobreescribir el asunto del correo |
| `--rate N` | Máx. mensajes por segundo (por defecto 3) |

## Cómo agregar una campaña nueva

Añade un bloque en `config.json` dentro de `campanias`:

```json
"mi_campania": {
  "descripcion": "Descripción corta",
  "asunto": "Asunto del correo",
  "plantilla": "nombre_de_archivo_en_templates",   // sin extensión: mi_campania.html / .txt
  "canales": ["email", "whatsapp"],
  "wa_template": "nombre_de_plantilla_de_meta",
  "wa_language": "es",
  "wa_image_url": null,
  "wa_body_params": ["param1", "param2"]           // o null si no usa variables
}
```

Luego crea las plantillas `templates/mi_campania.html` y `templates/mi_campania.txt`.
Placeholders disponibles: `__NOMBRE__`, `__USUARIO__`, `__PASSWORD__`, `__USUARIO_MOODLE__`.

## Deduplicación / historial

Cada vez que envías, el programa revisa `historial/historial.csv` y **no reenvía**
a quienes ya recibieron el mensaje en esa misma campaña y canal. Así puedes volver
a ejecutar sobre listados ampliados y solo se envían los nuevos.

## Formato de los listados

Se detecta automáticamente la cabecera (busca la columna `correo` o `email`).
Columnas reconocidas (por nombre, sin distinguir mayúsculas):

- `email` / `correo` — correo del estudiante
- `firstname`, `lastname`, `nombres`, `apellidos` — nombre
- `username` / `usuario moodle` — usuario
- `password` / `contraseña` / `clave` — contraseña
- `phone1` / `celular` / `telefono` — celular (formato Ecuador, ej. `+593991234567`)
# notificaciones_capacitate_manabi
