# Documentación de plantillas de WhatsApp (Meta Cloud API)

> Proyecto: **Notificador unificado — Capacítate Manabí (Prefectura de Manabí)**
> WABA ID: `913335414797060` · Phone Number ID: `1041789652353111` · API: `v21.0`

Este documento describe las **11 plantillas** configuradas en la cuenta de WhatsApp Business.
El catálogo se genera automáticamente con:

```bash
.venv/bin/python3 notificador.py plantillas --guardar
```

---

## Índice

- [Resumen general](#resumen-general)
- [Conceptos clave](#conceptos-clave)
- [Detalle de cada plantilla](#detalle-de-cada-plantilla)
- [Cómo mapear una plantilla a una campaña](#cómo-mapear-una-plantilla-a-una-campaña)

---

## Resumen general

| # | Plantilla | Idioma | Estado | Categoría | Header | Var. body | Botones |
|---|---|---|---|---|---|---|---|
| 1 | `sistema_de_vuelta` | es_EC | APPROVED | UTILITY | Imagen | — | 1 |
| 2 | `bienvenido_al_curso_..._hx380...` | es | APPROVED | UTILITY | Imagen | — | — |
| 3 | `copy_of_confirmacion_recibir_diploma_..._hx78b...` | es | APPROVED | UTILITY | Imagen | — | 1 (dinámico) |
| 4 | `copy_of_encuesta_evaluacion_satisfaccion_curso_..._hxfb5...` | es | APPROVED | MARKETING | — | nombre | 1 |
| 5 | `encuesta_evaluacion_satisfaccion_curso_..._hx098...` | es | APPROVED | UTILITY | — | nombre | 1 |
| 6 | `video_tutorial_como_ingresar_..._hx147...` | es | APPROVED | UTILITY | **Video** | — | — |
| 7 | `retoma_el_curso_..._hx2b6...` | es_MX | APPROVED | UTILITY | — | — | 2 |
| 8 | `copy_volver_al_curso_este_2026_con_imagen_..._hxe0...` | es | APPROVED | UTILITY | Imagen | nombre | — |
| 9 | `volver_al_curso_2026_001_..._hx31b...` | es_MX | APPROVED | MARKETING | — | nombre | 2 |
| 10 | `copy_reactivacion_inicio_curso_..._hx852...` | es_MX | APPROVED | MARKETING | — | nombre | 2 |
| 11 | `recordatorio_finalizacion_curso_2026_..._hx186...` | es_MX | APPROVED | MARKETING | — | nombre | 2 |

---

## Conceptos clave

- **Nombre con hash**: Meta añade un sufijo `_hx...` al nombre de la mayoría de
  plantillas. **Para enviar hay que usar el nombre completo**, incluido el hash.
  Solo `sistema_de_vuelta` no tiene hash.
- **Header**: elemento multimedia opcional arriba del mensaje. Puede ser
  `IMAGEN` o `VIDEO`. Si la plantilla lo define, el envío **debe** incluir la URL
  del recurso, o Meta devuelve error `132012`.
- **Variables de body**: marcadores `{{1}}`, `{{2}}`, … dentro del texto que se
  rellenan en el envío. Se pasan en orden como `body_params`.
- **Botones**: acciones rápidas (`URL`, `TELÉFONO`, `RESPUESTA RÁPIDA`). Los
  botones `URL` pueden tener una **URL dinámica** que incluye una variable
  `{{n}}` (se completa con `button_params`).
- **Categoría**: `UTILITY` (mensajes operativos) o `MARKETING` (promocionales).
  Afecta las restricciones de frecuencia y el tipo de plantilla permitida.

---

## Detalle de cada plantilla

### 1. `sistema_de_vuelta`
- **Idioma**: es_EC · **Categoría**: UTILITY · **ID**: `2227868991409595`
- **Header**: Imagen (obligatoria)
- **Variables de body**: ninguna
- **Botones**: "Ingresar" → `https://avmoodle.manabi.gob.ec/login/index.php`

**Texto del body:**
> Estimado/a participante, le informamos que la plataforma Moodle del Curso de
> Formación Ciudadana y Liderazgo Territorial, se encuentra nuevamente 100%
> operativa y habilitada para continuar con sus actividades de formación.
>
> Le invitamos a ingresar y retomar sus módulos de aprendizaje con normalidad.
>
> Prefectura de Manabí

**Uso actual**: campaña `reactivacion` (reactivación de la plataforma).

---

### 2. `bienvenido_al_curso_tu_usuario_ha_sido_activado_hx380221c39c837b641073287626de0cac`
- **Idioma**: es · **Categoría**: UTILITY · **ID**: `1332187778870267`
- **Header**: Imagen (obligatoria)
- **Variables de body**: ninguna
- **Botones**: ninguno

**Texto del body:**
> ✅ Usuario activado correctamente
>
> Estimado(a) participante: {{}}
>
> Le informamos que su acceso a la Escuela de Formación Ciudadana y Liderazgo
> Territorial ha sido habilitado exitosamente.
>
> 📚 A través de esta plataforma podrá acceder al curso en que se inscribió.
>
> 📧 Revise su correo electrónico para consultar sus credenciales e instrucciones
> de acceso. (En caso de que desee consultar alguna información escríbanos al
> número 097 869 6111.)
>
> Prefectura de Manabí
> Manabí cambia para siempre.

**Uso actual**: campaña `bienvenida` (credenciales de acceso).

---

### 3. `copy_of_confirmacion_recibir_diploma_hx78b8898f5f662260eb54c3ef82214c7e`
- **Idioma**: es · **Categoría**: UTILITY · **ID**: `1766339364533336`
- **Header**: Imagen (obligatoria)
- **Variables de body**: ninguna
- **Botones**: "Confirmar" → URL dinámica `https://forms.gle/zfFn1u2vtARGFna39{{1}}`

**Texto del body:**
> Para más información escríbenos al 593-99-309-6923.
>
> Confirme la recepción de su certificado haciendo clic en el botón de abajo. 👇

> ⚠️ El botón tiene una **URL dinámica**: el sufijo `{{1}}` se debe completar en el
> envío con `button_params`. Ejemplo: `{"index": 0, "text": "0"}`.

---

### 4. `copy_of_encuesta_evaluacion_satisfaccion_curso_hxfb519971e2a94b8577aa96dbc82f640a`
- **Idioma**: es · **Categoría**: MARKETING · **ID**: `4400983520216650`
- **Header**: ninguno
- **Variables de body**: `{{1}}` = nombre del participante
- **Botones**: "Responder encuesta" → `https://forms.gle/J276bN7NbizxrXHo6`

**Texto del body:**
> Hola, {{1}} 👋
>
> Gracias por haber participado en el curso Liderazgo y Participación Ciudadana.
>
> Tu opinión es muy importante para nosotros. Te invitamos a completar una breve
> encuesta de evaluación y satisfacción, que nos permitirá conocer tu experiencia
> y continuar mejorando nuestros procesos de formación.
>
> ⏱️ Completarla te tomará pocos minutos.
>
> Presiona el botón para responder la encuesta. 👇
>
> ¡Gracias por tu participación y por ayudarnos a seguir mejorando!
>
> Escuela de Formación Ciudadana y Liderazgo Territorial
> Prefectura de Manabí

---

### 5. `encuesta_evaluacion_satisfaccion_curso_hx0988cef75c4e41b3ae84a5fe2a03fcd8`
- **Idioma**: es · **Categoría**: UTILITY · **ID**: `1411640414154670`
- **Header**: ninguno
- **Variables de body**: `{{1}}` = nombre del participante
- **Botones**: "Responder encuesta" → `https://forms.gle/J276bN7NbizxrXHo6`

**Texto del body:** (idéntico a la plantilla 4)

> Hola, {{1}} 👋
>
> Gracias por haber participado en el curso Liderazgo y Participación Ciudadana.
>
> Tu opinión es muy importante para nosotros. Te invitamos a completar una breve
> encuesta de evaluación y satisfacción, que nos permitirá conocer tu experiencia
> y continuar mejorando nuestros procesos de formación.
>
> ⏱️ Completarla te tomará pocos minutos.
>
> Presiona el botón para responder la encuesta. 👇
>
> ¡Gracias por tu participación y por ayudarnos a seguir mejorando!
>
> Escuela de Formación Ciudadana y Liderazgo Territorial
> Prefectura de Manabí

> ℹ️ Diferencias con la plantilla 4: categoría (UTILITY vs MARKETING) y estado
> del ID. El contenido y el botón son iguales.

---

### 6. `video_tutorial_como_ingresar_hx14764eb48e5db34860be21afaec46e05`
- **Idioma**: es · **Categoría**: UTILITY · **ID**: `947977558142521`
- **Header**: **Video** (obligatorio)
- **Variables de body**: ninguna
- **Botones**: ninguno

**Texto del body:**
> ¿Cómo acceder al curso y la plataforma desde el teléfono?
>
> No lo olvides, si estás accediendo por primera vez, tu usuario y contraseña
> serán tu número de cédula.

> ⚠️ Única plantilla con header de **VIDEO**. En el envío debe usarse
> `header_video_url` con el enlace del `.mp4`.

---

### 7. `retoma_el_curso_hx2b6e1d0f14afc842c27f78ae79958534`
- **Idioma**: es_MX · **Categoría**: UTILITY · **ID**: `999144146109391`
- **Header**: ninguno
- **Variables de body**: ninguna
- **Botones**: 2
  - "Ingresar al curso" → `https://avmoodle.manabi.gob.ec/login/index.php`
  - "Más información" → `https://www.manabi.gob.ec/index.php/direccion-de-participacion-ciudadana/`

**Texto del body:**
> Te escribimos desde la Escuela de Formación Ciudadana de la Prefectura de Manabí.
>
> Si deseas continuar el curso "Liderazgo y Participación Ciudadana para la
> Gestión Local – Modalidad Virtual" ¡Puedes hacerlo hoy mismo!
>
> Solo dale click al botón de "Ingresar al curso", luego ingresa tu usuario y
> contraseña y listo.
>
> 🔐 Recuerda que si estás ingresando por primera vez, tu Usuario y tu Contraseña,
> son tu mismo número de cédula.
>
> Te esperamos.
>
> 👉 Si necesitas ayuda, escríbenos directamente por WhatsApp:
> 📱 +593995212193

**Uso actual**: campaña `recordatorio` (invitación a finalizar evaluación).

---

### 8. `copy_volver_al_curso_este_2026_con_imagen_hxe01222d18712ca4e9ba7947d74797d99`
- **Idioma**: es · **Categoría**: UTILITY · **ID**: `2085789498643210`
- **Header**: Imagen (obligatoria)
- **Variables de body**: `{{1}}` = nombre del participante
- **Botones**: ninguno

**Texto del body:**
> ¡Hola {{1}}! 👋 Tu camino en el curso de Liderazgo y Participación Ciudadana
> aún te espera. No es solo un curso, es la herramienta para que tu voz y tus
> proyectos dejen huella en tu comunidad.
>
> ¡El momento de liderar es ahora! 🚀

---

### 9. `volver_al_curso_2026_001_hx31b926418317d16afa24b69945bc2f43`
- **Idioma**: es_MX · **Categoría**: MARKETING · **ID**: `2213654819042235`
- **Header**: ninguno
- **Variables de body**: `{{1}}` = nombre del participante
- **Botones**: 2
  - "Ingresar al curso" → `https://avmoodle.manabi.gob.ec/login/index.php`
  - "Más información" → `https://www.manabi.gob.ec/index.php/direccion-de-participacion-ciudadana/`

**Texto del body:**
> Hola {{1}} 👋
>
> Te escribimos desde la Escuela de Formación Ciudadana de la Prefectura de Manabí.
>
> Sabemos que te matriculaste en el curso:
> 📘 "Liderazgo y Participación Ciudadana para la Gestión Local – Modalidad Virtual"
>
> ✨ Aunque ha pasado un tiempo, queremos decirte que Aún puedes ingresar y
> completar tu proceso de formación.
>
> Nunca es tarde para dar este paso.
>
> Te invitamos a ingresar hoy y comenzar tu camino como líder en tu comunidad.
>
> 🔐 Recuerda que si estás ingresando por primera vez, tu Usuario y tu Contraseña,
> son tu número de cédula.
>
> Te esperamos.
>
> 👉 Si necesitas ayuda, escríbenos directamente por WhatsApp:
> 📱 +593995212193
>
> Este mensaje ha sido enviado mediante los servicios de comunicación automatizada
> de CacicusTech. Por favor, no responder a este número.

---

### 10. `copy_reactivacion_inicio_curso_hx85243f432a2d943483e200801219390a`
- **Idioma**: es_MX · **Categoría**: MARKETING · **ID**: `1733054957664370`
- **Header**: ninguno
- **Variables de body**: `{{1}}` = nombre del participante
- **Botones**: 2
  - "Ingresar al curso" → `https://avmoodle.manabi.gob.ec/login/index.php`
  - "Más información" → `https://www.manabi.gob.ec/index.php/direccion-de-participacion-ciudadana/`

**Texto del body:** (similar a la plantilla 9, sin la línea de ayuda de WhatsApp)

> Hola {{1}} 👋
>
> Te escribimos desde la Escuela de Formación Ciudadana de la Prefectura de Manabí.
>
> Sabemos que te matriculaste en el curso:
> 📘 "Liderazgo y Participación Ciudadana para la Gestión Local – Modalidad Virtual"
>
> ✨ Aunque ha pasado un tiempo, queremos decirte que Aún puedes ingresar y
> completar tu proceso de formación.
>
> Nunca es tarde para dar este paso.
>
> Te invitamos a ingresar hoy y comenzar tu camino como líder en tu comunidad.
>
> 🔐 Recuerda que si estás ingresando por primera vez, tu Usuario y tu Contraseña,
> son tu número de cédula.
>
> Te esperamos.
>
> Este mensaje ha sido enviado mediante los servicios de comunicación automatizada
> de CacicusTech. Por favor, no responder a este número.

---

### 11. `recordatorio_finalizacion_curso_2026_hx18677e4448f28778948bd3ce4a2cd71b`
- **Idioma**: es_MX · **Categoría**: MARKETING · **ID**: `928640120081147`
- **Header**: ninguno
- **Variables de body**: `{{1}}` = nombre del participante
- **Botones**: 2
  - "Ingresar al curso" → `https://avmoodle.manabi.gob.ec/login/index.php`
  - "Más información" → `https://www.manabi.gob.ec/index.php/direccion-de-participacion-ciudadana/`

**Texto del body:**
> Hola {{1}} 👋
>
> Te escribimos desde la Escuela de Formación Ciudadana de la Prefectura de Manabí.
>
> Hemos identificado que estás muy cerca de finalizar el curso: "Liderazgo y
> Participación Ciudadana para la Gestión Local – Modalidad Virtual"
>
> 🎓 No te quedes sin tu certificado avalado por la UTM.
>
> ⏳ Aún estás a tiempo, Ingresa y culmina tu proceso esta semana.
>
> 🔐 Datos de acceso:
> Usuario: número de cédula
> Contraseña: número de cédula
>
> 📞 Si tienes alguna duda escríbenos al correo:
> 📧 escuela.virtual@manabi.gob.ec
> WhatsApp: 0982104735
>
> Este es un mensaje automático enviado a través de los servicios de comunicación
> de CacicusTech. Por favor, no responder a este mensaje.

---

## Cómo mapear una plantilla a una campaña

Cada campaña en `config.json` usa estos campos:

```jsonc
{
  "campanias": {
    "ejemplo": {
      "wa_template": "nombre_exacto_de_la_plantilla",   // con hash si lo tiene
      "wa_language": "es",                                // idioma exacto (es, es_EC, es_MX)
      "wa_image_url": "https://...",                      // si el header es IMAGEN
      "wa_body_params": ["Nombre del participante"]       // si el body tiene {{1}}
    }
  }
}
```

### Reglas para evitar errores

1. **`wa_template`**: usar SIEMPRE el nombre completo con hash (`_hx...`).
   - Ej. `retoma_el_curso` ❌ → `retoma_el_curso_hx2b6e1d0f14afc842c27f78ae79958534` ✅
2. **`wa_language`**: debe coincidir exactamente (`es`, `es_EC`, `es_MX`).
3. **Header imagen**: si la plantilla tiene header de imagen, `wa_image_url` es
   obligatorio (si no, error `132012`).
4. **Header video**: solo `video_tutorial_como_ingresar`. Requiere
   `header_video_url` (el programa lo soporta desde `enviar_plantilla_meta`).
5. **Variables `{{1}}`**: pasar `wa_body_params` en orden (uno por variable).
6. **Botones dinámicos**: solo `copy_of_confirmacion_recibir_diploma` tiene URL
   con `{{1}}`; se completa con `button_params`.

### Referencia de URLs de imagen/video

| Tipo | URL |
|---|---|
| Imagen de marca (usada en headers) | `https://cacicustech.com/capacitate_manabi/assets/694253231_1507359494090065_18027970677343898_n.jpg` |

---

*Generado automáticamente a partir de `plantillas_meta.json` (28-oct-2026).*
