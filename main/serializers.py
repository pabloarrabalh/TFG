"""
DRF Serializers for main app models.
"""
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

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


# ── User / Profile ────────────────────────────────────────────────────────────

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


# ── Notificaciones ────────────────────────────────────────────────────────────

class NotificacionSerializer(serializers.ModelSerializer):
    creada_en = serializers.DateTimeField(source='fecha_creada', read_only=True)

    class Meta:
        model = Notificacion
        fields = ['id', 'tipo', 'titulo', 'mensaje', 'leida', 'datos', 'creada_en']
        read_only_fields = ['id', 'tipo', 'titulo', 'mensaje', 'datos', 'creada_en']


# ── Amigos / Solicitudes ──────────────────────────────────────────────────────

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


# ── Plantilla ─────────────────────────────────────────────────────────────────

class PlantillaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plantilla
        fields = ['id', 'nombre', 'formacion', 'alineacion', 'privacidad', 'predeterminada', 'fecha_modificada']
        read_only_fields = ['id', 'fecha_modificada']


# ── Equipo / Jugador (read-only, for listings) ────────────────────────────────

class EquipoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Equipo
        fields = ['id', 'nombre', 'estadio']


class JugadorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Jugador
        fields = ['id', 'nombre', 'apellido', 'nacionalidad']
