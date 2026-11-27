"""
Outil 2 : le simulateur d'épargne.
 
Trois principes, tirés du métier :
- on distingue l'ENVELOPPE (assurance vie, PEA, PER, livret : un cadre fiscal et des frais)
et le SUPPORT (fonds euros, actions… : c'est lui qui porte le risque) ;
- un rendement n'est jamais certain : on simule 3 SCÉNARIOS (prudent, central, dynamique) ;
- on montre le capital en euros courants ET en euros constants (après inflation), et les frais payés.
 
Les taux réglementés viennent de parametres_2026.json ; les rendements des supports, les frais
et l'inflation sont des HYPOTHÈSES, rangées dans hypotheses_2026.json. La fiscalité à la sortie
n'est pas encore prise en compte.
"""
from agent_patrimonial.modeles import Client
from agent_patrimonial.outils.impot import calculer_impot
from agent_patrimonial.parametres import RACINE, charger_parametres, valeur

REGLEMENTAIRE = charger_parametres()
HYPOTHESES = charger_parametres(
    RACINE / "parametres" / "hypotheses_2026.json"
)
SCENARIOS = ("prudent", "central", "dynamique")


def _support(nom: str) -> dict:
    return valeur(HYPOTHESES, "supports", nom)


def _enveloppe(nom: str) -> dict:
    return valeur(HYPOTHESES, "enveloppes", nom)


def _taux_livret(enveloppe: str) -> float:
    """Retourne le taux réglementé du livret, identique dans les trois scénarios."""
    return valeur(REGLEMENTAIRE, "epargne_reglementee", f"{enveloppe}_taux")


def _plafond(enveloppe: str):
    """Retourne le plafond réglementaire de versements, ou None s'il n'y en a pas."""
    cle = _enveloppe(enveloppe)["plafond_versements"]
    if cle is None:
        return None

    rubrique = (
        "epargne_reglementee"
        if enveloppe in ("livret_a", "ldds")
        else "enveloppes"
    )
    return valeur(REGLEMENTAIRE, rubrique, cle)


def simuler_placement(
    enveloppe: str,
    support: str,
    capital_initial: float,
    versement_mensuel: float,
    duree_annees: int,
    deja_verse: float = 0.0,
) -> dict:
    """Simule un placement dans une enveloppe et un support, en trois scénarios."""
    if enveloppe not in HYPOTHESES["enveloppes"]:
        return {
            "erreur": (
                f"enveloppe inconnue : {enveloppe}. "
                f"Possibles : {list(HYPOTHESES['enveloppes'])}"
            )
        }

    env = _enveloppe(enveloppe)
    if support not in env["supports"]:
        return {
            "erreur": (
                f"le support {support} n'est pas proposé dans l'enveloppe "
                f"{enveloppe}. Supports possibles : {env['supports']}"
            )
        }

    montants = (capital_initial, versement_mensuel, duree_annees, deja_verse)
    if any(not isinstance(montant, (int, float)) for montant in montants):
        return {"erreur": "les montants et la durée doivent être numériques"}

    if any(montant < 0 for montant in montants):
        return {"erreur": "les montants et la durée ne peuvent pas être négatifs"}

    if isinstance(duree_annees, bool) or not isinstance(duree_annees, int):
        return {"erreur": "la durée doit être exprimée en nombre entier d'années"}

    sup = _support(support)
    inflation = valeur(HYPOTHESES, "inflation", "inflation_annuelle")
    nb_mois = duree_annees * 12
    total_verse = capital_initial + versement_mensuel * nb_mois

    resultats = {}
    for scenario in SCENARIOS:
        taux_brut = (
            _taux_livret(enveloppe)
            if support == "livret"
            else sup["rendement_scenarios"][scenario]
        )
        taux_net = (1 + taux_brut) * (1 - env["frais_gestion_annuels"]) - 1
        taux_mensuel = (1 + taux_net) ** (1 / 12) - 1

        capital = capital_initial * (1 - env["frais_versement"])
        frais_versement = capital_initial * env["frais_versement"]

        for _ in range(nb_mois):
            capital = (
                capital * (1 + taux_mensuel)
                + versement_mensuel * (1 - env["frais_versement"])
            )
            frais_versement += versement_mensuel * env["frais_versement"]

        capital_reel = capital / (1 + inflation) ** duree_annees

        resultats[scenario] = {
            "rendement_brut_pct": round(taux_brut * 100, 2),
            "capital_final_nominal": round(capital),
            "capital_final_reel": round(capital_reel),
            "gains_estimes": round(capital - total_verse),
            "frais_de_versement": round(frais_versement),
        }

    alertes = []
    plafond = _plafond(enveloppe)
    versements_cumules = deja_verse + total_verse

    if plafond is not None and versements_cumules > plafond:
        montant_formate = f"{versements_cumules:,.0f}".replace(",", " ")
        plafond_formate = f"{plafond:,.0f}".replace(",", " ")
        alertes.append(
            f"plafond de versements dépassé : {montant_formate} € "
            f"pour un plafond de {plafond_formate} €"
        )

    if duree_annees < sup["horizon_conseille"]:
        alertes.append(
            "durée inférieure à l'horizon conseillé pour ce support "
            f"({sup['horizon_conseille']} ans)"
        )

    if not sup["capital_garanti"]:
        alertes.append(
            "capital non garanti : sa valeur peut baisser, surtout sur une courte durée"
        )

    if enveloppe == "per":
        alertes.append(
            "sommes bloquées jusqu'à la retraite, sauf cas de déblocage anticipé"
        )

    return {
        "enveloppe": enveloppe,
        "support": support,
        "duree_annees": duree_annees,
        "total_verse": round(total_verse),
        "risque": sup["risque"],
        "capital_garanti": sup["capital_garanti"],
        "rendement_garanti": sup["rendement_garanti"],
        "inflation_retenue_pct": inflation * 100,
        "scenarios": resultats,
        "alertes": alertes,
        "hypotheses": (
            "rendements, frais et inflation : hypothèses du projet ; "
            "fiscalité à la sortie non prise en compte"
        ),
    }


def economie_impot_per(client: Client, versement_annuel: float) -> dict:
    """Estime l'économie d'impôt liée à la déduction d'un versement PER."""
    if not isinstance(versement_annuel, (int, float)) or isinstance(
        versement_annuel, bool
    ):
        return {"erreur": "le versement annuel doit être un montant numérique"}

    if versement_annuel < 0:
        return {"erreur": "le versement annuel ne peut pas être négatif"}

    avant = calculer_impot(
        client.revenu_imposable,
        client.situation_familiale,
        client.enfants_a_charge,
        client.pension_alimentaire_versee_annuelle,
    )
    apres = calculer_impot(
        max(client.revenu_imposable - versement_annuel, 0),
        client.situation_familiale,
        client.enfants_a_charge,
        client.pension_alimentaire_versee_annuelle,
    )

    economie = avant["impot_net_estime"] - apres["impot_net_estime"]

    return {
        "versement_annuel": round(versement_annuel),
        "impot_avant": avant["impot_net_estime"],
        "impot_apres": apres["impot_net_estime"],
        "economie_impot": round(economie),
        "cout_reel": round(versement_annuel - economie),
        "tmi_avant_pct": avant["tmi_pct"],
        "tmi_apres_pct": apres["tmi_pct"],
        "remarques": [
            "économie valable dans la limite du plafond de déduction PER du foyer "
            "(à vérifier sur l'avis d'imposition)",
            "l'économie d'aujourd'hui est en partie reprise à la sortie ; "
            "la fiscalité dépend du mode de sortie (rente ou capital)",
            "sommes bloquées jusqu'à la retraite, sauf cas de déblocage anticipé",
        ],
    }
