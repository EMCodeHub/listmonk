# Listmonk + Amazon SES

Despliegue reproducible de Listmonk con PostgreSQL, Caddy y Amazon SES como proveedor SMTP. El repositorio contiene solamente código, plantillas y parámetros operativos; no contiene listas de contactos, mensajes, volcados de bases de datos ni credenciales.

## Arquitectura

```text
Internet -> Caddy (HTTPS) -> Listmonk -> Amazon SES SMTP
                              |
                         PostgreSQL
```

Versiones principales fijadas:

- Listmonk `v5.1.0`
- PostgreSQL `17-alpine`
- Caddy `2.9-alpine`

## Requisitos

- Docker Engine y Docker Compose v2.
- Un dominio o subdominio apuntando al servidor para producción.
- Una identidad verificada en Amazon SES.
- Credenciales SMTP de SES de la misma región configurada.
- Puertos 80 y 443 accesibles. PostgreSQL no se publica.

## Instalación local

1. Clona el repositorio.
2. Copia la plantilla de configuración:

   ```bash
   cp .env.example .env
   ```

3. Genera contraseñas independientes y colócalas únicamente en `.env`:

   ```bash
   openssl rand -base64 36
   ```

4. Define al menos `POSTGRES_PASSWORD` y `LISTMONK_ADMIN_PASSWORD`.
5. Inicia los servicios:

   ```bash
   docker compose up -d
   ```

6. Abre `http://localhost` y comprueba el estado:

   ```bash
   docker compose ps
   docker compose logs --tail=100 listmonk
   ```

## Producción

Configura en `.env`:

```dotenv
APP_DOMAIN=mail.example.com
SITE_SCHEME=https
CADDY_ACME_EMAIL=operations@example.com
POSTGRES_USER=listmonk
POSTGRES_PASSWORD=<GENERAR_UN_VALOR_ALEATORIO>
POSTGRES_LISTMONK_DB=listmonk
LISTMONK_ADMIN_USERNAME=admin
LISTMONK_ADMIN_PASSWORD=<GENERAR_OTRO_VALOR_ALEATORIO>
SES_REGION=us-east-1
SES_SMTP_HOST=email-smtp.us-east-1.amazonaws.com
SES_SMTP_PORT=587
SES_SMTP_USERNAME=<CREDENCIAL_SMTP_SES>
SES_SMTP_PASSWORD=<SECRETO_SMTP_SES>
SES_FROM_EMAIL=verified-sender@example.com
SES_FROM_NAME=Listmonk
SES_MAX_SEND_RATE=10
```

Después ejecuta:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d
```

`.env`, `deploy/.env`, `secrets/` y todos los archivos de credenciales están ignorados por Git. No copies credenciales dentro de YAML, TOML, scripts o documentación.

## Amazon SES y velocidad de envío

La plantilla conserva `SES_MAX_SEND_RATE=10` mensajes por segundo. Antes de enviar:

1. Verifica el dominio remitente, DKIM, SPF y DMARC.
2. Confirma que la cuenta SES esté fuera del sandbox.
3. Consulta la cuota y el máximo de envío por segundo de la región.
4. Establece `SES_MAX_SEND_RATE` por debajo o igual a la cuota real.
5. Mantén la configuración SMTP operativa actual: puerto `587`, `STARTTLS`, hasta `10` conexiones, reintentos limitados y verificación TLS activa.
6. Configura el procesamiento de rebotes y quejas antes de campañas reales.
7. Empieza con una campaña pequeña y revisa reputación, hard bounces y complaints.

No aumentes la concurrencia y la tasa simultáneamente. La tasa efectiva debe respetar siempre el menor valor entre la configuración local y la cuota concedida por SES.

## Datos excluidos

El `.gitignore` bloquea explícitamente:

- `clean_emails_real_estate/` y `listmonk_emails/`.
- CSV/TXT de suscriptores, rebotes y listas de correo.
- Mensajes `.eml`, `.mbox` y `.pst`.
- `.env`, secretos, claves y archivos de credenciales.
- Volcados `.sql`, `.dump`, migraciones con datos y copias de seguridad.

Comprueba antes de cada publicación:

```bash
git status --short
git diff --cached --name-only
```

## Backups

Los datos persistentes viven en volúmenes de Docker. Crea un backup fuera del repositorio antes de actualizar:

```bash
docker compose exec -T postgres pg_dump \
  -U "$POSTGRES_USER" -d "$POSTGRES_LISTMONK_DB" \
  --no-owner --no-acl > /ruta/segura/listmonk.sql
```

No elimines el volumen `postgres_data` salvo que quieras borrar deliberadamente la base de datos.

## Seguridad

- Usa contraseñas únicas y aleatorias.
- Limita permisos de `.env` y archivos de secretos a `600` en producción.
- No publiques el puerto 5432 ni el puerto interno 9000.
- Rota inmediatamente cualquier credencial expuesta accidentalmente.
- Ejecuta una revisión de secretos sobre el índice de Git antes de cada `push`.
