import math

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db.models import Sum
from rest_framework import serializers

from .views.utils import shield_name
from .models import *


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name  = serializers.CharField(max_length=150, required=False, default='')
    email      = serializers.EmailField()
    username   = serializers.CharField(max_length=150)
    password1  = serializers.CharField(write_only=True)
    password2  = serializers.CharField(write_only=True)

    def validate_username(self, value):
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('Ese nombre de usuario ya está en uso.')
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Ese email ya está registrado.')
        return value

    def validate(self, data):
        if data['password1'] != data['password2']:
            raise serializers.ValidationError({'password2': 'Las contraseñas no coinciden.'})
        try:
            validate_password(data['password1'])
        except Exception as e:
            raise serializers.ValidationError({'password1': list(e.messages)})
        return data

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password1'],
            first_name=validated_data['first_name'],
            last_name=validated_data.get('last_name', ''),
        )


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['nickname', 'estado', 'preferencias_notificaciones']


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    foto_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'profile', 'foto_url']
        read_only_fields = ['id']

    def get_foto_url(self, obj):
        try:
            if obj.profile.foto:
                return obj.profile.foto.url
        except Exception:
            pass
        return None

    def validate_username(self, value):
        value = value.strip()
        user = self.instance
        qs = User.objects.filter(username__iexact=value)
        if user:
            qs = qs.exclude(pk=user.pk)
        if qs.exists():
            raise serializers.ValidationError('Ese nombre de usuario ya está en uso.')
        return value


class NotificacionSerializer(serializers.ModelSerializer):
    creada_en = serializers.DateTimeField(source='fecha_creada', read_only=True)

    class Meta:
        model = Notificacion
        fields = ['id', 'tipo', 'titulo', 'mensaje', 'leida', 'datos', 'creada_en']
        read_only_fields = ['id', 'tipo', 'titulo', 'mensaje', 'datos', 'creada_en']


class SolicitudAmistadSerializer(serializers.ModelSerializer):
    emisor_username = serializers.CharField(source='emisor.username', read_only=True)
    emisor_nombre   = serializers.CharField(source='emisor.first_name', read_only=True)
    receptor_username = serializers.CharField(source='receptor.username', read_only=True)

    class Meta:
        model = SolicitudAmistad
        fields = ['id', 'estado', 'emisor_username', 'emisor_nombre', 'receptor_username', 'fecha_creada']
        read_only_fields = fields


class AmistadSerializer(serializers.ModelSerializer):
    amigo_id         = serializers.SerializerMethodField()
    amigo_username   = serializers.SerializerMethodField()
    amigo_first_name = serializers.SerializerMethodField()
    amigo_foto       = serializers.SerializerMethodField()

    class Meta:
        model = Amistad
        fields = ['id', 'amigo_id', 'amigo_username', 'amigo_first_name', 'amigo_foto']

    def _amigo(self, obj):
        req = self.context.get('request')
        return obj.usuario2 if obj.usuario1 == req.user else obj.usuario1

    def get_amigo_id(self, obj):       return self._amigo(obj).id
    def get_amigo_username(self, obj): return self._amigo(obj).username
    def get_amigo_first_name(self, obj): return self._amigo(obj).first_name

    def get_amigo_foto(self, obj):
        try:
            return self._amigo(obj).profile.foto.url
        except Exception:
            return None


class PlantillaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plantilla
        fields = ['id', 'nombre', 'formacion', 'alineacion', 'privacidad', 'predeterminada', 'fecha_modificada']
        read_only_fields = ['id', 'fecha_modificada']


class EquipoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Equipo
        fields = ['id', 'nombre', 'estadio']


class JugadorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Jugador
        fields = ['id', 'nombre', 'apellido', 'nacionalidad']


class TemporadaSerializer(serializers.ModelSerializer):
    display = serializers.SerializerMethodField()

    class Meta:
        model = Temporada
        fields = ['id', 'nombre', 'display']

    def get_display(self, obj):
        return obj.nombre.replace('_', '/')


class JugadorListSerializer(serializers.ModelSerializer):
    posicion = serializers.SerializerMethodField()

    class Meta:
        model = Jugador
        fields = ['id', 'nombre', 'apellido', 'nacionalidad', 'posicion']

    def get_posicion(self, obj):
        return obj.get_posicion_mas_frecuente() or ''


class EquipoListSerializer(serializers.ModelSerializer):
    escudo = serializers.SerializerMethodField()
    jugadores_count = serializers.SerializerMethodField()

    class Meta:
        model = Equipo
        fields = ['id', 'nombre', 'estadio', 'escudo', 'jugadores_count']

    def get_escudo(self, obj):
        return shield_name(obj.nombre)

    def get_jugadores_count(self, obj):
        temporada = Temporada.objects.order_by('-nombre').first()
        if not temporada:
            return 0
        return EquipoJugadorTemporada.objects.filter(equipo=obj, temporada=temporada).count()


class PrediccionSerializer(serializers.ModelSerializer):
    jornada_numero = serializers.IntegerField(source='jornada.numero_jornada', read_only=True)
    temporada = serializers.CharField(source='jornada.temporada.nombre', read_only=True)
    prediccion = serializers.SerializerMethodField()
    real = serializers.SerializerMethodField()

    class Meta:
        model = PrediccionJugador
        fields = ['id', 'jugador_id', 'jornada_id', 'jornada_numero', 'temporada','prediccion', 'modelo', 'creada_en', 'real']
        read_only_fields = ['id', 'creada_en', 'jornada_numero', 'temporada', 'real']

    def get_prediccion(self, obj):
        val = obj.prediccion
        if val is None:
            return None
        try:
            if math.isnan(val) or math.isinf(val):
                return None
            return round(val, 2)
        except (TypeError, ValueError):
            return None

    def get_real(self, obj):
        pts = EstadisticasPartidoJugador.objects.filter(
            jugador=obj.jugador,
            partido__jornada=obj.jornada,
        ).aggregate(s=Sum('puntos_fantasy'))['s']
        if pts is None:
            return None
        try:
            if math.isnan(pts) or math.isinf(pts):
                return None
            return float(pts)
        except (TypeError, ValueError):
            return None


class PrediccionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrediccionJugador
        fields = ['jugador', 'jornada', 'prediccion', 'modelo']

    def validate(self, data):
        qs = PrediccionJugador.objects.filter(
            jugador=data['jugador'],
            jornada=data['jornada'],
            modelo=data.get('modelo', 'xgb'),
        )
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                'Ya existe una predicción para este jugador, jornada y modelo.'
            )
        return data
