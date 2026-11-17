"""
Le chargement des paramètres réglementaires
(taux, plafonds, barème, seuils).

Chaque paramètre est rangé dans un fichier JSON avec sa valeur, son unité,
sa source, sa date d'entrée en vigueur et sa date de vérification.

Les paramètres ne sont donc jamais écrits en dur dans le code :
on les met à jour dans le fichier, sans toucher au code.
"""

import json
from datetime import date
from pathlib import Path


RACINE = Path(__file__).resolve().parents[2]
FICHIER_PARAMETRES = RACINE / "parametres" / "parametres_2026.json"

# Au-delà de 6 mois sans vérification, un paramètre est signalé.
AGE_MAX_JOURS = 180


def charger_parametres(
    chemin: Path = FICHIER_PARAMETRES,
) -> dict:
    """Lit le fichier des paramètres et renvoie son contenu."""
    with chemin.open(encoding="utf-8") as fichier:
        return json.load(fichier)


def valeur(
    parametres: dict,
    rubrique: str,
    nom: str,
):
    """
    Renvoie la valeur d'un paramètre.

    Exemple :
    valeur(parametres, "epargne_reglementee", "livret_a_taux")
    """
    return parametres[rubrique][nom]["valeur"]


def parametres_a_surveiller(
    parametres: dict,
    aujourd_hui: date | None = None,
) -> list[str]:
    """
    Liste les paramètres à vérifier :

    - paramètres explicitement marqués ``a_verifier`` ;
    - paramètres vérifiés il y a plus de 180 jours.
    """
    aujourd_hui = aujourd_hui or date.today()
    alertes: list[str] = []

    for rubrique, contenu in parametres.items():
        if not isinstance(contenu, dict):
            continue

        for nom, parametre in contenu.items():
            if not isinstance(parametre, dict):
                continue

            if parametre.get("a_verifier"):
                note = parametre.get(
                    "note",
                    "valeur non confirmée",
                )
                alertes.append(
                    f"{rubrique}.{nom} : à vérifier ({note})"
                )

            elif parametre.get("date_verification"):
                date_verification = date.fromisoformat(
                    parametre["date_verification"]
                )
                age = (aujourd_hui - date_verification).days

                if age > AGE_MAX_JOURS:
                    alertes.append(
                        f"{rubrique}.{nom} : "
                        f"vérifié il y a {age} jours"
                    )

    return alertes
