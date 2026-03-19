# Dashboard de cierre de cartera agrícola

App en Streamlit lista para correr localmente o desplegar en Railway usando Docker.

## Estructura

- `app.py`: dashboard principal
- `data/dashboard/*.csv|json`: salidas del pipeline
- `data/qc/*.csv`: auditoría y calidad
- `requirements.txt`: dependencias
- `Dockerfile`: despliegue portable para Railway

## Ejecutar local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Desplegar en Railway

1. Subí esta carpeta a un repo de GitHub.
2. En Railway, creá un proyecto nuevo y elegí **Deploy from GitHub repo**.
3. Railway detectará el `Dockerfile` y construirá la app.
4. Cuando termine el build, la app quedará publicada.

## Actualizar datos

Reemplazá estos archivos con los generados por tu pipeline:

- `data/dashboard/dashboard_points.csv`
- `data/dashboard/dashboard_cultivo.csv`
- `data/dashboard/dashboard_provincia.csv`
- `data/dashboard/dashboard_depto.csv`
- `data/dashboard/dashboard_asegurado.csv`
- `data/dashboard/dashboard_kpis.json`
- `data/qc/perfil_calidad_campos.csv`
- `data/qc/duplicados_exactos.csv`
- `data/qc/duplicados_negocio.csv`

## Idea de evolución

- agregar login simple
- mover las salidas a S3 / GCS
- sumar mapas por departamento con shapefiles
- agregar módulo de renovación y priorización comercial
