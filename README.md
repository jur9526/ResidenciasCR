# Residencias Costa Rica

Panel y sitio estático de propiedades (demo). 

## Cómo ejecutar localmente

1. Abre Terminal en este directorio:

```bash
cd /Users/jurgenarleyelizondo/ResidenciasCostaRica
```

2. Inicia servidor local (recomendado):

- Python 3:
  ```bash
  python3 -m http.server 8000
  ```

- Python 2:
  ```bash
  python -m SimpleHTTPServer 8000
  ```

3. Visita en navegador:

- `http://localhost:8000/index.html` (sitio público)
- `http://localhost:8000/admin.html` (admin)

> Si no se usa servidor, abrir `index.html` y `admin.html` directamente con doble clic puede funcionar, pero es posible que algunos fetchs fallen por políticas CORS.

## Admin

- Contraseña: `Jurgen`
- Agregar/editar/eliminar propiedades con formulario
- Estatísticas de propiedades en la barra superior
- Exportar JSON con el botón "Exportar JSON"
- Restaurar datos de `properties-data.js` con botón "Restaurar"

## Datos

- `properties-data.js`: lista base en `window.DEFAULT_PROPERTIES`
- `localStorage` llave: `rcr_properties`

## Problemas comunes

- Form submit falla si no hay Internet (usa `https://api.web3forms.com/submit`) -> escribe por WhatsApp directamente.
- Si imagen no carga, hay fallback en el front.

## Notas de desarrollo

- `main.js`: lógica pública del listado de propiedades
- `admin.html`: interfaz y CRUD con `localStorage`
