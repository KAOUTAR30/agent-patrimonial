"""
Outil 3 : l'épargne de précaution et le contrôle de conformité (l'adéquation au client).

- L'épargne de précaution se calcule sur les DÉPENSES ESSENTIELLES du client, pas sur son revenu.
- Le contrôle de conformité regarde le risque du SUPPORT (pas de l'enveloppe), l'horizon, les
  connaissances, la capacité à supporter une perte, l'épargne de précaution, les plafonds et l'endettement.

Le résultat distingue ce qui BLOQUE, ce qui demande une ALERTE, et les CONDITIONS à remplir.
Attention : « CONFORME » veut seulement dire qu'aucune règle du modèle ne s'est déclenchée ;
ce n'est pas une validation : la décision appartient toujours au conseiller.
"""
from agent_patrimonial.modeles import Client
from agent_patrimonial.outils.epargne import HYPOTHESES, REGLEMENTAIRE, _plafond
from agent_patrimonial.parametres import valeur

NIVEAUX_RISQUE = ["aucun", "faible", "moyen", "élevé"]
RISQUE_MAX = {"prudent": "faible", "équilibré": "moyen", "dynamique": "élevé"}


def epargne_precaution(client: Client) -> dict:
    """Compare l'épargne disponible au besoin de précaution (N mois de dépenses essentielles)."""
    mois = valeur(REGLEMENTAIRE, "regles_conseil", "epargne_precaution_mois_depenses")
    besoin = client.depenses_essentielles_mensuelles * mois
    disponible = client.epargne.disponible()
    manque = max(besoin - disponible, 0)
    return {"mois_retenus": mois, "besoin": round(besoin), "disponible": round(disponible),
            "manque": round(manque), "suffisante": manque == 0}


def controler_conformite(client: Client, enveloppe: str, support: str, montant: float = 0.0) -> dict:
    """Vérifie si un placement (enveloppe + support) peut être proposé à un client."""
    bloquants, alertes, conditions = [], [], []

    if enveloppe not in HYPOTHESES["enveloppes"]:
        return {"decision": "BLOQUANT", "bloquants": [f"enveloppe inconnue : {enveloppe}"],
                "alertes": [], "conditions": [], "enveloppe": enveloppe, "support": support}
    env = valeur(HYPOTHESES, "enveloppes", enveloppe)
    if support not in env["supports"]:
        return {"decision": "BLOQUANT", "bloquants": [f"le support {support} n'existe pas dans l'enveloppe {enveloppe}"],
                "alertes": [], "conditions": [], "enveloppe": enveloppe, "support": support}
    sup = valeur(HYPOTHESES, "supports", support)

    # 1. Le risque du SUPPORT, comparé au risque maximal accepté par le profil
    depassement = NIVEAUX_RISQUE.index(sup["risque"]) - NIVEAUX_RISQUE.index(RISQUE_MAX[client.profil_risque])
    if depassement >= 2:
        bloquants.append(f"risque {sup['risque']} incompatible avec un profil {client.profil_risque}")
    elif depassement == 1:
        alertes.append(f"risque {sup['risque']} au-dessus du profil {client.profil_risque}")
        conditions.append("limiter ce support à une petite part de l'épargne")

    # 2. L'horizon du client, comparé à celui conseillé pour le support
    if client.horizon_annees < sup["horizon_conseille"]:
        bloquants.append(f"horizon du client ({client.horizon_annees} ans) inférieur à celui du support "
                         f"({sup['horizon_conseille']} ans)")

    # 3. La capacité à supporter une perte
    if not sup["capital_garanti"] and client.perte_max_acceptable_pct == 0:
        bloquants.append("le client n'accepte aucune perte, et le capital de ce support n'est pas garanti")

    # 4. Les connaissances : un débutant face à un support risqué
    if client.connaissances == "débutant" and sup["risque"] in ("moyen", "élevé"):
        alertes.append("client débutant face à un support risqué")
        conditions.append("expliquer le risque de perte en capital avant toute souscription")

    # 5. L'épargne de précaution, avant tout placement non disponible immédiatement
    precaution = epargne_precaution(client)
    if sup["liquidite"] != "immédiate" and not precaution["suffisante"]:
        alertes.append(f"épargne de précaution insuffisante : il manque {precaution['manque']:,} €".replace(",", " "))
        conditions.append("constituer d'abord l'épargne de précaution")

    # 6. Le plafond de versements de l'enveloppe
    plafond = _plafond(enveloppe)
    deja_place = getattr(client.epargne, enveloppe, 0.0)
    if plafond is not None and deja_place + montant > plafond:
        bloquants.append(f"plafond dépassé : {deja_place:,.0f} € déjà placés + {montant:,.0f} € > {plafond:,.0f} €".replace(",", " "))

    # 7. Le PER : bloqué jusqu'à la retraite, d'un intérêt limité près de la retraite
    if enveloppe == "per":
        conditions.append("expliquer que les sommes sont bloquées jusqu'à la retraite, sauf déblocage anticipé")
        if client.age >= 60 or client.statut == "retraité":
            alertes.append("client proche de la retraite ou retraité : l'intérêt du PER est limité")

    # 8. L'endettement, signalé quand il dépasse le seuil du secteur
    seuil = valeur(REGLEMENTAIRE, "regles_conseil", "taux_endettement_max") * 100
    if client.taux_endettement_pct() > seuil:
        alertes.append(f"taux d'endettement élevé ({client.taux_endettement_pct()} % pour un seuil de {seuil:.0f} %)")

    decision = "BLOQUANT" if bloquants else ("ALERTE" if alertes else "CONFORME")
    return {"enveloppe": enveloppe, "support": support, "decision": decision,
            "bloquants": bloquants, "alertes": alertes, "conditions": conditions}