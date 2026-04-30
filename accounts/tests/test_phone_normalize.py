"""Tests de normalisation des numéros sénégalais en E.164."""
import pytest
from django.core.exceptions import ValidationError

from accounts.models import normalize_phone_sn


class TestNormalizePhone:
    """normalize_phone_sn doit toujours produire +221XXXXXXXXX ou raise."""

    @pytest.mark.parametrize("raw,expected", [
        # Déjà E.164
        ("+221770001234", "+221770001234"),
        # Avec préfixe sans +
        ("221770001234", "+221770001234"),
        # Format national 9 chiffres
        ("770001234", "+221770001234"),
        # Avec espaces (formats courants saisis par les clients)
        ("+221 77 000 12 34", "+221770001234"),
        ("77 000 12 34", "+221770001234"),
        ("+221  77  000  12  34", "+221770001234"),
        # Avec tirets / parenthèses
        ("+221-77-000-12-34", "+221770001234"),
        ("(+221) 77 000 12 34", "+221770001234"),
        # Numéros 30/33 (fixe Sénégal)
        ("338234567", "+221338234567"),
        ("+221338234567", "+221338234567"),
    ])
    def test_valid_formats(self, raw, expected):
        assert normalize_phone_sn(raw) == expected

    @pytest.mark.parametrize("raw", [
        "",
        None,
        "abc",
        "12345",            # trop court
        "+33612345678",     # numéro français, pas sénégalais
        "+22177",           # tronqué
        "770001234567",     # trop long
        "880001234",        # ne commence pas par 7 ou 3
        "200001234",        # ne commence pas par 7 ou 3
    ])
    def test_invalid_formats(self, raw):
        with pytest.raises(ValidationError):
            normalize_phone_sn(raw)
