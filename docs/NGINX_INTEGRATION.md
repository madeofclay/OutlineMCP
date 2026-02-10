# Integración con Nginx Existente

Este documento explica cómo integrar el proxy MCP con tu configuración de Nginx existente.

## Estado Actual del Servidor

- **Dominio**: data-dev.clay.cl
- **SSL**: Let's Encrypt (Certbot configurado)
- **Nginx**: Configuración en `/etc/nginx/nginx.conf`
- **Auth**: Basic auth con `/etc/nginx/.htpasswd`
- **Proxies internos**:
  - localhost:6006 (proxy principal)
  - localhost:8080 (docs, api_gracia)
  - localhost:8001 (api_accounts_plan)
  - localhost:8002 (categorization)

## Nuevo Proxy MCP

- **Aplicación**: FastAPI en localhost:8000
- **URL**: `https://data-dev.clay.cl/outline/`
- **Puerto Nginx**: 443 (HTTPS) - Ya configurado
- **Certificado**: Reutiliza el existente de data-dev.clay.cl

## Pasos de Integración

### Paso 1: Ejecutar Instalación

```bash
cd /home/ec2-user/repos/OutlineMCP
sudo bash install.sh
```

Esto instala:
- Docker
- Python virtual environment (con uv)
- Dependencias del proxy
- Systemd service (mcp-proxy)

**NO modifica Nginx** (evita conflictos con tu configuración existente)

### Paso 2: Integrar con Nginx

Después de que `install.sh` complete:

#### 2a. Ver el template de configuración

```bash
cat /home/ec2-user/repos/OutlineMCP/nginx-location.conf
```

Verás algo como:

```nginx
location /outline/ {
    proxy_pass http://localhost:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # WebSocket support
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";

    # Timeouts
    proxy_connect_timeout 90s;
    proxy_send_timeout 90s;
    proxy_read_timeout 90s;
}
```

#### 2b. Agregar a tu Nginx

Edita `/etc/nginx/nginx.conf`:

```bash
sudo nano /etc/nginx/nginx.conf
```

Busca el bloque `server` para port 443 (HTTPS) y agrega el location **antes del cierre**:

```nginx
server {
    listen 443 ssl http2;
    # ... SSL config y otros locations ...

    # Agrega aquí:
    location /outline/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_connect_timeout 90s;
        proxy_send_timeout 90s;
        proxy_read_timeout 90s;
    }

    # ... resto de la configuración ...
}
```

#### 2c. Validar configuración

```bash
sudo nginx -t
```

Debería mostrar:
```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

#### 2d. Recargar Nginx

```bash
sudo systemctl reload nginx
```

### Paso 3: Verificar

```bash
# Verificar que el proxy está corriendo
systemctl status mcp-proxy

# Verificar Nginx
systemctl status nginx

# Probar el endpoint
curl https://data-dev.clay.cl/outline/health
```

Deberías obtener:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-10T...",
  "containers_tracked": 0,
  "containers_running": 0
}
```

## Características Heredadas de Nginx

El proxy MCP **automáticamente reutiliza**:

✅ **SSL/TLS**: Certificado Let's Encrypt de data-dev.clay.cl
✅ **Auth**: Sistema `/etc/nginx/.htpasswd` (si lo activas en location)
✅ **Headers**: X-Real-IP, X-Forwarded-For, etc.
✅ **WebSocket**: Soportado (headers Upgrade/Connection)

## Endpoints Disponibles

Una vez integrado:

### Health Check
```bash
curl https://data-dev.clay.cl/outline/health
```

### Stats (con auth opcional)
```bash
curl -u admin:password https://data-dev.clay.cl/outline/stats
```

### Main Proxy
```bash
curl -H "X-Outline-API-Key: outline_..." https://data-dev.clay.cl/outline/...
```

## Opcionales: Mejorar Configuración

### Agregar Auth Básica

Si quieres proteger el proxy con auth:

```nginx
location /outline/ {
    # ... config existente ...

    auth_basic "Clay Restricted Content";
    auth_basic_user_file /etc/nginx/.htpasswd;
}
```

### Agregar Rate Limiting

Si quieres limitar requests:

```nginx
location /outline/ {
    # ... config existente ...

    limit_req zone=mcp_limit burst=40 nodelay;
}
```

(Requiere definir `limit_req_zone` en el bloque http)

## Troubleshooting

### Error: Connection refused (localhost:8000)

El proxy FastAPI no está corriendo:

```bash
sudo systemctl start mcp-proxy
sudo systemctl status mcp-proxy
journalctl -u mcp-proxy -f
```

### Error: 502 Bad Gateway

Nginx no puede conectar al proxy:

```bash
# Verificar que el proxy está escuchando
sudo netstat -tuln | grep 8000

# Ver logs de Nginx
sudo tail -f /var/log/nginx/error.log

# Ver logs del proxy
journalctl -u mcp-proxy -n 50
```

### Error: Nginx config syntax error

Después de editar:

```bash
sudo nginx -t
# Muestra línea con error
```

Verifica los cambios y repite.

## Gestión del Proxy

### Ver estado
```bash
systemctl status mcp-proxy
```

### Ver logs en tiempo real
```bash
journalctl -u mcp-proxy -f
```

### Reiniciar
```bash
sudo systemctl restart mcp-proxy
```

### Ver contenedores
```bash
docker ps -a --filter "name=mcp-"
```

### Limpiar Nginx cache (si es necesario)
```bash
sudo systemctl reload nginx
```

## Documentación Relacionada

- **README.md**: Guía completa de usuario y admin
- **proxy.py**: Código del proxy FastAPI
- **install.sh**: Script de instalación
- **nginx-location.conf**: Template de configuración Nginx

## Soporte

Si necesitas:

1. **Cambiar URL**: Edita el location en nginx.conf
2. **Cambiar puerto**: Modifica proxy.py línea ~130 (CONTAINER_MEMORY, etc.)
3. **Agregar seguridad**: Usa auth_basic en el location
4. **Debuguear**: Revisa logs con `journalctl -u mcp-proxy -f`
