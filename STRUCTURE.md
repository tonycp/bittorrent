# Estructura del repositorio

Este fichero ofrece una vista concisa de la estructura del proyecto y **apunta a los manifiestos** de cada componente como fuente de verdad cuando se hable de estructura, comandos de build/run e información de despliegue.

## Proyectos

### **Componentes y manifiestos**

- **bit_lib**: manifiesto en `bit_lib/MANIFEST.yml`. Documentación en `bit_lib/docs/`.
- **tracker**: manifiesto en `tracker/MANIFEST.yml`. Documentación en `tracker/docs/`.
- **client**: manifiesto en `client/MANIFEST.yml`. Documentación en `tracker/docs/`.
- **plantillas**: plantilla general en `wiki_torrent/manifest_template.yml`.

### **Cómo usar los manifiestos**

- **Construir**: ejecutar `uv build --directory <componente>` según el manifiesto del componente.
- **Instalar (desarrollo)**: `pip install -e <componente>` (cuando el manifiesto lo recomendar).
- **Ejecutar ejemplo**: consulte la clave `uv.run_example` en `*/MANIFEST_uv.yml` para el comando sugerido de ejecución.

### **Dónde documentar cambios de estructura**

- Modifique el manifiesto correspondiente (`*/MANIFEST.yml` o `*/MANIFEST_uv.yml`) cuando cambie la estructura de un componente (nuevas carpetas, entrypoints, puertos expuestos, etc.).
- Use `bit_lib/docs/` y `tracker/docs/` para detallar protocolos, esquemas y ejemplos de uso; el manifiesto debe apuntar a esos directorios.

### **Notas rápidas**

- Los manifiestos son la fuente canónica para CI/CD y automaciones que necesiten conocer rutas, comandos de build/run y puertos.
- Mantenga los manifiestos mínimos y actualizados; los documentos en `*/docs/` pueden ser más extensos y humanos.
