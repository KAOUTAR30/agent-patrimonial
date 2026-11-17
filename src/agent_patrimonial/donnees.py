"""
Le chargement des clients.

Les clients sont lus dans le fichier JSON, puis vérifiés un par un avec le modèle `Client`.
Si un client est mal rempli, on affiche TOUTES les erreurs d'un coup, avec l'identifiant
du client concerné, au lieu de s'arrêter à la première.
"""
import json
from pathlib import Path

from pydantic import ValidationError

from agent_patrimonial.modeles import Client

# Le dossier racine du projet : deux niveaux au-dessus de ce fichier (src/agent_patrimonial/)
RACINE = Path(__file__).resolve().parents[2]
FICHIER_CLIENTS = RACINE / "data" / "clients_fictifs.json"


def charger_clients(chemin: Path = FICHIER_CLIENTS) -> dict[str, Client]:
    """Lit et vérifie les clients. Renvoie un dictionnaire {identifiant: client}."""
    with open(chemin, encoding="utf-8") as f:
        donnees = json.load(f)

    clients, erreurs = {}, []
    for brut in donnees:
        try:
            client = Client(**brut)                    # Pydantic vérifie chaque champ
            clients[client.id_client] = client
        except ValidationError as e:
            for err in e.errors():
                champ = ".".join(str(x) for x in err["loc"])
                erreurs.append(f"{brut.get('id_client', '?')} – {champ} : {err['msg']}")

    if erreurs:
        raise ValueError("Clients invalides :\n" + "\n".join(erreurs))
    if len(clients) != len(donnees):
        raise ValueError("Deux clients ont le même identifiant")
    return clients
