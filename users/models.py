# users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser

class Evaluador(AbstractUser):
    # Asegúrate de que tu modelo tenga estos campos
    cargo = models.CharField(max_length=255, blank=True, verbose_name="Cargo o Puesto")
    foto = models.ImageField(upload_to='fotos/', null=True, blank=True, verbose_name="Foto de Perfil")
    firma_digital = models.ImageField(upload_to='firmas/', null=True, blank=True, verbose_name="Firma Digital (PNG)")
    es_gerente = models.BooleanField(default=False, verbose_name="¿Es el Gerente que firma por defecto?")

    def __str__(self):
        return self.get_full_name() or self.username

class Institucion(models.Model):
    nombre = models.CharField(max_length=255, verbose_name="Nombre de la Institución")
    ubicacion = models.CharField(max_length=255, blank=True, verbose_name="Ubicación (ej. Ciudad, Estado)")

    class Meta:
        verbose_name = "Institución"
        verbose_name_plural = "Instituciones"

    def __str__(self):
        return self.nombre

class Curso(models.Model):
    nombre = models.CharField(max_length=255, verbose_name="Nombre del Curso")
    
    class Meta:
        verbose_name = "Definición de Curso"
        verbose_name_plural = "Definiciones de Cursos"

    def __str__(self):
        return self.nombre

class Participante(models.Model):
    nombre_completo = models.CharField(max_length=255)
    email = models.EmailField(unique=True, help_text="El correo debe ser único para cada participante.")
    titulo = models.CharField(max_length=50, blank=True, null=True, verbose_name="Título Profesional (ej. Q.F.B.)")
    institucion = models.ForeignKey(
        Institucion, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Institución de Origen"
    )

    class Meta:
        verbose_name = "Participante"
        verbose_name_plural = "Participantes"

    def __str__(self):
        return self.nombre_completo

class Constancia(models.Model):
    participante = models.ForeignKey(Participante, on_delete=models.CASCADE, verbose_name="Participante")
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, verbose_name="Curso")
    fecha_inicio = models.DateField(verbose_name="Fecha de Inicio del Evento")
    fecha_termino = models.DateField(verbose_name="Fecha de Término del Evento")
    duracion_en_horas = models.DecimalField(max_digits=4, decimal_places=1, verbose_name="Duración (Horas)")
    firma_gerente = models.ForeignKey(
        Evaluador,
        on_delete=models.PROTECT,
        related_name="constancias_como_gerente",
        verbose_name="Firma del Gerente"
    )
    firma_especialista = models.ForeignKey(
        Evaluador,
        on_delete=models.PROTECT,
        related_name="constancias_como_especialista",
        verbose_name="Firma del Especialista"
    )
    fecha_emision = models.DateField(auto_now_add=True, verbose_name="Fecha de Emisión")
    codigo_verificacion = models.CharField(max_length=20, unique=True, blank=True, verbose_name="Código de Verificación")
    es_webinar = models.BooleanField(default=False, verbose_name="¿Es de Webinar?")
    fecha_vencimiento = models.DateField(null=True, blank=True, verbose_name="Fecha de Vencimiento")


    class Meta:
        verbose_name = "Constancia"
        verbose_name_plural = "Constancias"
        unique_together = ('participante', 'curso', 'fecha_inicio')

    def __str__(self):
        return f"Constancia para {self.participante} en el curso {self.curso}"