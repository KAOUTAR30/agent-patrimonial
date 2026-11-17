"""
La structure unique des données du projet.

Chaque client est décrit par le modèle `Client`. Pydantic vérifie automatiquement,
au chargement, que chaque champ existe, qu'il a le bon type et une valeur autorisée.
Un client mal rempli provoque une erreur claire, au lieu d'un calcul faux plus tard.

Règle du projet : l'agent part des informations dont dispose le conseiller
(avis d'imposition, versements constatés, biens déclarés). Il ne calcule que ce
que ces documents ne donnent pas : l'effet d'une décision future.
"""
from typing import Literal

from pydantic import BaseModel, Field

# Les valeurs autorisées pour les champs à choix
SituationFamiliale = Literal["célibataire", "marié", "pacsé", "divorcé", "veuf"]
ProfilRisque = Literal["prudent", "équilibré", "dynamique"]
Connaissances = Literal["débutant", "intermédiaire", "expert"]
Statut = Literal["actif", "retraité", "sans emploi"]
TypeBien = Literal["résidence principale", "résidence secondaire", "locatif"]


class Epargne(BaseModel):
    """Les montants déjà placés par le client, en euros (0 par défaut)."""
    compte_courant: float = Field(0, ge=0)
    livret_a: float = Field(0, ge=0)
    ldds: float = Field(0, ge=0)
    assurance_vie: float = Field(0, ge=0)
    pea: float = Field(0, ge=0)
    per: float = Field(0, ge=0)

    def disponible(self) -> float:
        """L'épargne disponible immédiatement : compte courant et livrets."""
        return self.compte_courant + self.livret_a + self.ldds

    def total(self) -> float:
        """La somme de toute l'épargne."""
        return sum(self.model_dump().values())


class BienImmobilier(BaseModel):
    """Un bien immobilier du client (informations déclarées)."""
    type_bien: TypeBien
    valeur_estimee: float = Field(gt=0)                    # la valeur du bien aujourd'hui
    capital_restant_du: float = Field(0, ge=0)             # ce qui reste à rembourser sur le crédit
    loyers_annuels_percus: float = Field(0, ge=0)          # bien locatif : déjà inclus dans le revenu imposable
    taxe_fonciere_annuelle: float = Field(0, ge=0)         # la taxe foncière payée chaque année

    def valeur_nette(self) -> float:
        """La valeur du bien, moins la dette qui reste dessus."""
        return self.valeur_estimee - self.capital_restant_du


class FiscaliteDeclaree(BaseModel):
    """Les informations de l'avis d'imposition du client (le constat, pas un calcul)."""
    impot_revenu_annuel: float = Field(ge=0)               # l'impôt payé, lu sur l'avis
    nombre_parts: float = Field(gt=0)                      # le nombre de parts, lu sur l'avis
    revenu_fiscal_reference: float = Field(ge=0)           # le revenu fiscal de référence


class Client(BaseModel):
    """Le profil d'un client, tel qu'il est recueilli au premier rendez-vous."""
    id_client: str = Field(pattern=r"^C\d{3}$")                   # par exemple « C001 »
    nom: str
    age: int = Field(ge=18, le=110)
    situation_familiale: SituationFamiliale
    enfants_a_charge: int = Field(0, ge=0, le=15)
    statut: Statut

    # Revenus et dépenses
    revenu_imposable: float = Field(ge=0)                         # annuel, AVANT déduction de la pension alimentaire
    revenu_net_mensuel: float = Field(ge=0)
    prestations_sociales_mensuelles: float = Field(0, ge=0)       # aides de la CAF constatées sur le compte (non imposables)
    pension_alimentaire_versee_annuelle: float = Field(0, ge=0)   # déductible du revenu imposable
    depenses_essentielles_mensuelles: float = Field(ge=0)         # logement, alimentation, transport…
    mensualites_credits: float = Field(0, ge=0)                   # toutes les mensualités de crédit
    capacite_epargne_mensuelle: float = Field(ge=0)

    # Fiscalité déclarée (l'avis d'imposition)
    fiscalite: FiscaliteDeclaree

    # Patrimoine
    epargne: Epargne = Epargne()
    immobilier: list[BienImmobilier] = []                         # vide si le client n'a pas de bien

    # Objectif et profil investisseur
    objectif: str
    horizon_annees: int = Field(ge=0, le=50)
    profil_risque: ProfilRisque
    connaissances: Connaissances
    perte_max_acceptable_pct: float = Field(ge=0, le=100)         # la perte que le client peut supporter

    def patrimoine_immobilier_net(self) -> float:
        """La valeur nette de tous les biens immobiliers."""
        return sum(bien.valeur_nette() for bien in self.immobilier)

    def patrimoine_net(self) -> float:
        """Le patrimoine total : l'épargne et l'immobilier net."""
        return self.epargne.total() + self.patrimoine_immobilier_net()

    def taux_endettement_pct(self) -> float:
        """La part des revenus mensuels consacrée aux crédits."""
        revenus = self.revenu_net_mensuel + self.prestations_sociales_mensuelles
        return round(self.mensualites_credits / revenus * 100, 1) if revenus else 0.0
