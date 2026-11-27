"""
Outil 1 : l'impôt sur le revenu.

Deux usages, selon la règle du projet :
- le CONSTAT : l'impôt actuel du client se lit sur son avis d'imposition (client.fiscalite) ;
- la SIMULATION : on calcule l'impôt avec le barème, pour mesurer l'effet d'une décision
  (un versement PER, un changement de situation). Le calcul sert aussi à vérifier la cohérence
  avec l'avis : un gros écart signale des réductions ou crédits d'impôt que le modèle ne connaît pas.

Les chiffres (barème, plafond, décote) viennent de parametres_2026.json, jamais du code.
C'est une estimation simplifiée : ni réductions ni crédits d'impôt, ni plafonds spécifiques
(parent isolé, invalidité), ni contribution sur les hauts revenus.
"""
from agent_patrimonial.modeles import Client
from agent_patrimonial.parametres import charger_parametres, valeur

PARAMETRES = charger_parametres()


def _p(nom):
    """Raccourci : la valeur d'un paramètre de la rubrique impot_revenu."""
    return valeur(PARAMETRES, "impot_revenu", nom)


def calculer_parts(situation: str, enfants: int) -> float:
    """Le nombre de parts fiscales du foyer (règles simplifiées)."""
    en_couple = situation in ("marié", "pacsé")
    veuf_avec_enfants = situation == "veuf" and enfants > 0

    parts = 2.0 if (en_couple or veuf_avec_enfants) else 1.0   # un veuf avec enfants garde les parts d'un couple
    parts += 0.5 * min(enfants, 2)                             # +0,5 part pour chacun des deux premiers enfants
    parts += 1.0 * max(enfants - 2, 0)                         # +1 part à partir du troisième
    if situation in ("célibataire", "divorcé") and enfants > 0:
        parts += 0.5                                           # parent isolé (case T) : +0,5 part
    return parts


def _impot_bareme(revenu: float, parts: float) -> float:
    """Le barème progressif, appliqué au revenu divisé par le nombre de parts (le quotient familial)."""
    quotient, impot, plancher = revenu / parts, 0.0, 0.0
    for plafond, taux in _p("bareme_tranches"):
        plafond = float("inf") if plafond is None else plafond   # la dernière tranche n'a pas de plafond
        if quotient > plancher:
            impot += (min(quotient, plafond) - plancher) * taux
        plancher = plafond
    return impot * parts


def tranche_marginale(revenu: float, parts: float) -> float:
    """Le taux de la dernière tranche atteinte (TMI), en %."""
    quotient = revenu / parts
    for plafond, taux in _p("bareme_tranches"):
        if plafond is None or quotient <= plafond:
            return taux * 100
    return 0.0


def calculer_impot(revenu_imposable: float, situation: str, enfants: int,
                   pension_alimentaire_versee: float = 0.0) -> dict:
    """Estime l'impôt sur le revenu d'un foyer, et renvoie le détail du calcul."""
    if revenu_imposable < 0 or enfants < 0 or pension_alimentaire_versee < 0:
        raise ValueError("Le revenu, le nombre d'enfants et la pension ne peuvent pas être négatifs.")

    revenu_net = max(revenu_imposable - pension_alimentaire_versee, 0.0)   # la pension est déductible
    parts = calculer_parts(situation, enfants)
    parts_base = 2.0 if (situation in ("marié", "pacsé") or (situation == "veuf" and enfants > 0)) else 1.0

    # 1. Plafonnement du quotient familial : l'avantage des demi-parts supplémentaires est limité
    impot_avec_parts = _impot_bareme(revenu_net, parts)
    impot_sans_parts = _impot_bareme(revenu_net, parts_base)
    avantage_max = (parts - parts_base) * 2 * _p("plafond_demi_part")
    plafonne = (impot_sans_parts - impot_avec_parts) > avantage_max
    impot_brut = impot_sans_parts - avantage_max if plafonne else impot_avec_parts

    # 2. Décote pour les petits impôts
    seul = parts_base == 1.0
    seuil = _p("decote_seuil_seul") if seul else _p("decote_seuil_couple")
    montant = _p("decote_montant_seul") if seul else _p("decote_montant_couple")
    decote = max(0.0, montant - _p("decote_taux") * impot_brut) if impot_brut < seuil else 0.0
    impot_net = max(impot_brut - decote, 0.0)

    return {
        "revenu_imposable": round(revenu_imposable),
        "pension_deduite": round(pension_alimentaire_versee),
        "revenu_net_imposable": round(revenu_net),
        "parts_fiscales": parts,
        "impot_brut": round(impot_brut),
        "plafonnement_quotient_familial": plafonne,
        "decote": round(min(decote, impot_brut)),
        "impot_net_estime": round(impot_net),
        "taux_moyen_pct": round(impot_net / revenu_net * 100, 1) if revenu_net else 0.0,
        "tmi_pct": tranche_marginale(revenu_net, parts),
        "estimation": True,
        "bareme": PARAMETRES["impot_revenu"]["bareme_tranches"]["source"],
    }


def impot_du_client(client: Client) -> dict:
    """Estime l'impôt d'un client à partir de son profil."""
    return calculer_impot(client.revenu_imposable, client.situation_familiale,
                          client.enfants_a_charge, client.pension_alimentaire_versee_annuelle)


def comparer_avec_avis(client: Client, seuil_pct: float = 5.0, seuil_euros: float = 300.0) -> dict:
    """Compare l'impôt estimé à celui de l'avis d'imposition, et explique un éventuel écart."""
    calcul = impot_du_client(client)
    avis = client.fiscalite
    ecart = calcul["impot_net_estime"] - avis.impot_revenu_annuel
    ecart_pct = ecart / avis.impot_revenu_annuel * 100 if avis.impot_revenu_annuel else 0.0

    remarques = []
    if calcul["parts_fiscales"] != avis.nombre_parts:
        remarques.append(f"nombre de parts différent : {calcul['parts_fiscales']} calculées, "
                         f"{avis.nombre_parts} sur l'avis (situation particulière à vérifier)")
    if abs(ecart_pct) > seuil_pct and abs(ecart) > seuil_euros:
        remarques.append("écart important : le client a sans doute des réductions ou crédits d'impôt "
                         "(emploi à domicile, garde d'enfants, dons…) que l'estimation ne connaît pas")

    return {"impot_avis": round(avis.impot_revenu_annuel), "impot_estime": calcul["impot_net_estime"],
            "ecart": round(ecart), "ecart_pct": round(ecart_pct, 1),
            "coherent": not remarques, "remarques": remarques}