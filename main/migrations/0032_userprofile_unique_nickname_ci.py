from django.db import migrations, models
from django.db.models import Q
from django.db.models.functions import Lower


def _unique_candidate(base: str, profile_id: int, attempt: int = 0) -> str:
    suffix = f"_{profile_id}" if attempt == 0 else f"_{profile_id}_{attempt}"
    trimmed_base = (base or "")[: max(1, 100 - len(suffix))]
    return f"{trimmed_base}{suffix}"


def dedupe_nicknames(apps, schema_editor):
    UserProfile = apps.get_model("main", "UserProfile")

    seen = set()
    for profile in UserProfile.objects.order_by("id"):
        raw = (profile.nickname or "").strip()

        # Keep empty nickname as empty (constraint ignores blank nicknames)
        if not raw:
            if profile.nickname != "":
                profile.nickname = ""
                profile.save(update_fields=["nickname"])
            continue

        lowered = raw.lower()
        if lowered not in seen:
            seen.add(lowered)
            if raw != profile.nickname:
                profile.nickname = raw
                profile.save(update_fields=["nickname"])
            continue

        # Duplicate detected: generate a deterministic unique fallback
        attempt = 0
        candidate = _unique_candidate(raw, profile.id, attempt)
        while UserProfile.objects.exclude(id=profile.id).filter(nickname__iexact=candidate).exists():
            attempt += 1
            candidate = _unique_candidate(raw, profile.id, attempt)

        profile.nickname = candidate
        profile.save(update_fields=["nickname"])
        seen.add(candidate.lower())


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0031_userprofile_photo_folder"),
    ]

    operations = [
        migrations.RunPython(dedupe_nicknames, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="userprofile",
            constraint=models.UniqueConstraint(
                Lower("nickname"),
                condition=~Q(nickname=""),
                name="uniq_userprofile_nickname_ci_nonempty",
            ),
        ),
    ]
