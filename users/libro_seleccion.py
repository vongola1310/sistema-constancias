def preparar_seleccion_libro(sesiones, seleccion=None):
    """Identificadores por hoja/fila; los datos y la elegibilidad provienen del Excel."""
    hojas = set(seleccion.get('hojas', [])) if seleccion is not None else set()
    alumnos = set(seleccion.get('alumnos', [])) if seleccion is not None else None
    resultado = []
    for indice_sesion, sesion in enumerate(sesiones):
        personas = []
        for indice_persona, persona in enumerate(sesion['personas']):
            identificador = f'{indice_sesion}:{indice_persona}'
            correo = (persona.get('email') or '').strip().lower()
            habilitado = bool(sesion['seleccionable'] and persona['aprueba'] and correo)
            personas.append({
                **persona, 'seleccion_id': identificador, 'correo_seleccion': correo,
                'habilitado': habilitado,
                'seleccionado': habilitado and (alumnos is None or identificador in alumnos),
            })
        resultado.append({
            **sesion, 'personas': personas, 'seleccion_indice': indice_sesion,
            'marcada': sesion['seleccionable'] and sesion['hoja'] in hojas,
        })
    return resultado
