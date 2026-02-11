# Configuración de Claude Desktop con Outline MCP Proxy

## Descripción General

Esta guía te ayuda a configurar Claude Desktop en tu máquina cliente para conectarse al servidor proxy Outline MCP instalado en EC2.

**Flujo de comunicación:**
```
Claude Desktop (tu máquina)
    ↓ HTTPS
Nginx Proxy (data-dev.clay.cl/outline)
    ↓ HTTP
FastAPI Proxy (puerto 8000)
    ↓
Docker Container (MCP Outline)
    ↓
Tus documentos en Outline
```

---

## Requisitos

- ✅ Claude Desktop instalado
- ✅ API key válido de Outline (comienza con `outline_`)
- ✅ Acceso a `https://data-dev.clay.cl/outline` (debe estar disponible desde tu red)

---

## Paso 1: Obtener tu API Key de Outline

### En tu instancia de Outline:

1. Haz clic en tu **avatar** (esquina superior derecha)
2. Selecciona **"Settings"** → **"API Tokens"**
3. Haz clic en **"Create token"**
4. Copia el token (comienza con `outline_`)
5. **Guárdalo en un lugar seguro** - no lo compartas

**Ejemplo:**
```
outline_aBcDeFgHiJkLmNoPqRsT1234567890uvwxyz
```

---

## Paso 2: Configurar Claude Desktop

### **Para Linux:**

#### 2a. Verificar que existe el archivo de configuración

```bash
# Crear directorio si no existe
mkdir -p ~/.config/Claude

# Verificar si el archivo ya existe
cat ~/.config/Claude/claude_desktop_config.json
```

Si el archivo ya existe, continúa al paso 2b. Si no existe, crea uno vacío:

```bash
echo '{}' > ~/.config/Claude/claude_desktop_config.json
```

#### 2b. Editar la configuración

```bash
nano ~/.config/Claude/claude_desktop_config.json
```

Reemplaza el contenido con:

```json
{
  "mcpServers": {
    "outline": {
      "url": "https://data-dev.clay.cl/outline",
      "transport": {
        "type": "streamableHttp"
      },
      "headers": {
        "X-Outline-API-Key": "outline_TU_API_KEY_AQUI"
      }
    }
  }
}
```

**Pasos para guardar:**
1. Reemplaza `outline_TU_API_KEY_AQUI` con tu API key real
2. Presiona `Ctrl + O` (guarda)
3. Presiona `Enter` (confirma)
4. Presiona `Ctrl + X` (cierra)

---

### **Para macOS:**

#### 2a. Abrir el archivo de configuración

```bash
# Crear directorio si no existe
mkdir -p ~/.config/Claude

# Abrir con editor de texto predeterminado
open ~/.config/Claude/claude_desktop_config.json
```

O usar Terminal:
```bash
nano ~/.config/Claude/claude_desktop_config.json
```

#### 2b. Pegar la configuración

Reemplaza el contenido con:

```json
{
  "mcpServers": {
    "outline": {
      "url": "https://data-dev.clay.cl/outline",
      "transport": {
        "type": "streamableHttp"
      },
      "headers": {
        "X-Outline-API-Key": "outline_TU_API_KEY_AQUI"
      }
    }
  }
}
```

Reemplaza `outline_TU_API_KEY_AQUI` con tu API key real.

#### 2c. Guardar

- Si usas `nano`: `Ctrl + O` → `Enter` → `Ctrl + X`
- Si usas editor gráfico: `Cmd + S`

---

### **Para Windows:**

#### 2a. Abrir el Explorador de Archivos

Presiona `Win + R` y escribe:
```
%APPDATA%\Claude\
```

Luego presiona `Enter`.

#### 2b. Abrir `claude_desktop_config.json`

Si el archivo **no existe**, créalo:
1. Haz clic derecho en el espacio vacío
2. Selecciona "Crear" → "Documento de texto"
3. Nómbralo `claude_desktop_config.json`

Si el archivo **ya existe**, haz clic derecho y selecciona "Abrir con" → "Bloc de notas" o tu editor preferido.

#### 2c. Pegar la configuración

Reemplaza el contenido con:

```json
{
  "mcpServers": {
    "outline": {
      "url": "https://data-dev.clay.cl/outline",
      "transport": {
        "type": "streamableHttp"
      },
      "headers": {
        "X-Outline-API-Key": "outline_TU_API_KEY_AQUI"
      }
    }
  }
}
```

Reemplaza `outline_TU_API_KEY_AQUI` con tu API key real.

#### 2d. Guardar

Presiona `Ctrl + S` (o usa el menú Archivo → Guardar).

---

## Paso 3: Reiniciar Claude Desktop

**IMPORTANTE:** Cierra **completamente** Claude Desktop y vuelve a abrirlo.

En Windows/Mac: Cierra desde el Dock o Task Manager.
En Linux: `pkill -f "Claude Desktop"` o cierra desde el menú.

---

## Paso 4: Verificar la conexión

Después de reiniciar, deberías ver:

1. En la esquina **inferior derecha** de Claude Desktop: un punto verde ✅ junto a "outline"
2. Si está en rojo ❌: hay un problema de conexión

**Si está verde, ¡estás listo!** Prueba escribiendo algo como:
- "¿Qué documentos tengo en Outline?"
- "Busca documentos sobre [tema]"
- "Crea un resumen de mis notas"

---

## Troubleshooting

### ❌ Problema: "outline" aparece en rojo (desconectado)

**Posibles causas:**

#### 1. JSON inválido

Verifica que el JSON sea válido:
- Usa un validador: https://jsonlint.com/
- Asegúrate de que:
  - No haya comas extras
  - Las comillas sean " (no ' ni caracteres especiales)
  - Las llaves { } estén pareadas

**Ejemplo válido:**
```json
{
  "mcpServers": {
    "outline": {
      "url": "https://data-dev.clay.cl/outline",
      "transport": {
        "type": "streamableHttp"
      },
      "headers": {
        "X-Outline-API-Key": "outline_xxxxx"
      }
    }
  }
}
```

#### 2. API key incorrecta

Verifica que:
- Comience con `outline_` (no `ol_api_`)
- No tenga espacios extras al principio o final
- Sea el token completo

Prueba en terminal:
```bash
curl -H "Authorization: Bearer outline_TU_API_KEY" \
  https://app.getoutline.com/api/auth.info \
  -d '{}' -H "Content-Type: application/json"
```

Si ves `"error"`, tu API key es inválido. Regenera uno nuevo en Outline.

#### 3. URL incorrecta

Verifica que la URL sea exactamente:
```
https://data-dev.clay.cl/outline
```

Prueba en el navegador:
```
https://data-dev.clay.cl/outline/health
```

Debería ver:
```json
{"status":"healthy",...}
```

Si no funciona, el proxy no está disponible. Contacta al administrador.

#### 4. Problema de red/firewall

Si todo lo anterior está bien pero sigue desconectado:
- Verifica que puedas acceder a `https://data-dev.clay.cl` desde tu navegador
- Si usas VPN corporativa, asegúrate de estar conectado
- Si usas firewall personal, verifica que no bloquee HTTPS a ese dominio

---

### ❌ Problema: "No puedo conectarme al servidor"

**Solución:**

1. Cierra Claude Desktop completamente
2. Abre Terminal/Cmd y verifica la URL:

```bash
# Linux/Mac
curl -k https://data-dev.clay.cl/outline/health

# Windows (PowerShell)
(Invoke-WebRequest -Uri "https://data-dev.clay.cl/outline/health" -SkipCertificateCheck).Content
```

Debería retornar:
```json
{"status":"healthy",...}
```

Si retorna error:
- El proxy no está operativo (contacta al admin)
- Tu red bloquea el acceso (configura VPN o firewall)
- La URL es incorrecta (verifica paso 2)

---

### ❌ Problema: "Invalid API key"

**Solución:**

1. Ve a Outline → Settings → API Tokens
2. **Elimina** el token actual
3. Crea uno **nuevo**
4. Copia el token completo (sin espacios)
5. Actualiza `claude_desktop_config.json`
6. Reinicia Claude Desktop

---

### ⚠️ Problema: Respuestas lentas o timeouts

**Posibles causas:**

1. **Primera request es lenta (5-10 segundos)**
   - Es normal - Claude Desktop está creando un contenedor Docker
   - Las requests subsecuentes serán más rápidas

2. **Timeout después de 90 segundos**
   - El proxy tiene timeout de 90s para crear contenedores
   - Si la imagen es muy grande, puede excederse
   - Contacta al admin para aumentar el timeout

3. **Contenedor crasheando**
   - El admin puede revisar los logs:
     ```bash
     docker logs mcp-xxxxx
     ```

---

## Configuración Avanzada

### Múltiples instancias de Outline

Si tienes múltiples servidores Outline, puedes configurar ambos:

```json
{
  "mcpServers": {
    "outline-prod": {
      "url": "https://data-dev.clay.cl/outline",
      "transport": {"type": "streamableHttp"},
      "headers": {"X-Outline-API-Key": "outline_xxxxx"}
    },
    "outline-staging": {
      "url": "https://staging.example.com/outline",
      "transport": {"type": "streamableHttp"},
      "headers": {"X-Outline-API-Key": "outline_yyyyy"}
    }
  }
}
```

---

## Pruebas después de configurar

1. **Test básico:**
   ```
   "¿Estás conectado a Outline?"
   ```
   Claude debería responder que sí.

2. **Test de lectura:**
   ```
   "Dame un resumen de mis documentos en Outline"
   ```

3. **Test de búsqueda:**
   ```
   "Busca documentos sobre [tema]"
   ```

4. **Test de creación (si tienes permisos):**
   ```
   "Crea un documento con el título 'Test desde Claude'"
   ```

---

## Soporte

Si nada funciona después de seguir estos pasos:

1. Verifica que el archivo JSON sea válido (https://jsonlint.com/)
2. Verifica que tu API key sea válido (comienza con `outline_`)
3. Verifica que puedas acceder a `https://data-dev.clay.cl/outline/health`
4. Reinicia Claude Desktop completamente
5. Contacta al administrador del proxy con:
   - Tu API key hash (primeros 8 caracteres)
   - El error exacto que ves
   - Tu sistema operativo

---

## Preguntas Frecuentes

**P: ¿Puedo usar la misma API key en múltiples máquinas?**
R: Sí, la misma API key puede usarse en todas tus máquinas.

**P: ¿Mi API key está segura en el archivo de configuración?**
R: El archivo está en tu máquina local. No se comparte a menos que lo hagas deliberadamente.

**P: ¿Qué pasa si pierdo mi API key?**
R: Regenera uno nuevo en Outline Settings → API Tokens. El antiguo dejará de funcionar.

**P: ¿Por qué la primera request tarda 5-10 segundos?**
R: El proxy crea un contenedor Docker bajo demanda. Las siguientes serán más rápidas.

**P: ¿Puedo usar esto sin internet?**
R: No, necesitas conectividad a `https://data-dev.clay.cl` y a `https://app.getoutline.com`.

---

## Versión del documento

- Última actualización: 2026-02-11
- Compatible con: Claude Desktop v1.0+
- Proxy versión: 1.0.0

