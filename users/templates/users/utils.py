# users/utils.py
import os
from io import BytesIO
from django.http import HttpResponse
from django.template.loader import get_template
from django.conf import settings
from xhtml2pdf import pisa

def render_to_pdf(template_src, context_dict={}):
    """
    Función helper para generar PDF compatible con Vercel
    """
    template = get_template(template_src)
    html  = template.render(context_dict)
    result = BytesIO()

    # Esta función ayuda a xhtml2pdf a encontrar las imágenes (Logos, firmas)
    def link_callback(uri, rel):
        """
        Convierte URLs de HTML a rutas absolutas del sistema para que 
        el motor de PDF pueda leer los archivos.
        """
        # Si es un archivo MEDIA (Fotos de perfil, Firmas en Cloudinary)
        if uri.startswith(settings.MEDIA_URL):
            # En Cloudinary, la URL ya es absoluta (https://...), así que la dejamos pasar.
            # xhtml2pdf la descargará de internet.
            return uri
            
        # Si es un archivo STATIC (CSS, Logo del sitio)
        elif uri.startswith(settings.STATIC_URL):
            path = os.path.join(settings.STATIC_ROOT, uri.replace(settings.STATIC_URL, ""))
            if not os.path.isfile(path):
                # Fallback para desarrollo (cuando no has corrido collectstatic)
                path = os.path.join(settings.BASE_DIR, 'static', uri.replace(settings.STATIC_URL, ""))
            return path
            
        return uri

    # Generar el PDF
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result, link_callback=link_callback)
    
    if not pdf.err:
        return result.getvalue()
    return None