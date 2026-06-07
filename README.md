# Annot8 Backend

Annot8 es una aplicación backend para la gestión colaborativa de documentos
multimodales. Permite registrar usuarios, crear equipos y proyectos, subir
documentos PDF, definir regiones sobre sus páginas y trabajar con esquemas y
anotaciones.

Este documento describe como instalar y desplegar la aplicación en un entorno
local usando Docker Compose.

## Requisitos previos

Antes de empezar es necesario tener instalado:

- Docker
- Docker Compose
- Git

No es necesario instalar Python ni MySQL directamente en la máquina local, ya
que ambos se ejecutan dentro de contenedores.

## Estructura del despliegue

El despliegue local se compone de los siguientes servicios:

- `backend`: API desarrollada con FastAPI.
- `db`: base de datos MySQL.
- `files_server`: servidor Nginx para servir los archivos subidos.
- `caddy`: proxy inverso que expone la API y los archivos al exterior.

La base de datos y los archivos subidos se almacenan en volumenes de Docker, por
lo que no se pierden al apagar los contenedores.

## Instalación

Clonar el repositorio:

```bash
git clone <URL_DEL_REPOSITORIO>
cd TFG_MAST_Backend
```

Crear un archivo `.env` en la raíz del proyecto con las variables necesarias:

```env
MYSQL_ROOT_PASSWORD=change_this_password
SECRET_KEY=clave_secreta_para_firmar_tokens
FILES_BASE_URL=http://localhost/files
```

Estas variables se usan para configurar MySQL, la firma de los tokens de sesión y la
URL pública desde la que se sirven los archivos subidos.

## Despliegue local

Construir y levantar los contenedores:

```bash
docker compose up -d --build
```

Comprobar que los servicios estan en ejecución:

```bash
docker compose ps
```

Ver los logs del backend:

```bash
docker compose logs -f backend
```

La API quedara disponible en:

```text
http://localhost/api
```

La documentación interactiva de Swagger se puede consultar en:

```text
http://localhost/api/docs
```

## Gestión de archivos subidos

Los documentos PDF subidos por los usuarios se guardan en el volumen
`uploads_data`. Dentro del contenedor del backend este volumen se monta en:

```text
/uploads
```

Dentro del contenedor `files_server`, el mismo volumen se monta en:

```text
/usr/share/nginx/html
```

Por esta razón, el backend es el encargado de escribir los archivos y Nginx se
encarga de servirlos en modo solo lectura.

Para listar los archivos subidos desde el backend:

```bash
docker exec -it mast_backend ls -R /uploads
```

Para listarlos desde el servidor de archivos:

```bash
docker exec -it mast_files ls -R /usr/share/nginx/html
```

## Ejecución de pruebas

Con los contenedores levantados, las pruebas pueden ejecutarse dentro del
contenedor del backend:

```bash
docker compose run --rm backend bash -c "PYTHONPATH=/app pytest -v"
```

También se puede ejecutar un módulo concreto de pruebas, por ejemplo el de los esquemas de anotación:

```bash
docker compose exec backend bash -c "cd /app && python -m pytest tests/test_schemas.py -v"
```

## Parar la aplicación

Para detener los contenedores:

```bash
docker compose down
```

Este comando no elimina los volumenes, por lo que la base de datos y los archivos
subidos se conservan.

Si se desea eliminar también todos los datos persistentes:

```bash
docker compose down -v
```

Este último comando borra la base de datos y los archivos subidos, por lo que
debe usarse solo cuando se quiera reiniciar completamente el entorno local.

## Puertos

Por defecto, Caddy expone la aplicación en los puertos `80` y `443`.

Si alguno de estos puertos ya esta ocupado en la máquina local, se pueden
modificar en `docker-compose.yml`, dentro del servicio `caddy`.
