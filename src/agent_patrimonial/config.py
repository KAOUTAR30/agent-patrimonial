"""
Les réglages de l'agent, lus dans le fichier .env à la racine du projet.

Le fichier .env est propre à chaque machine (VM de travail, Mac, serveur) et n'est jamais
envoyé sur GitHub. Le fichier .env.example montre les réglages à remplir.
Si un réglage manque, on utilise la valeur par défaut indiquée ici.
"""
import os

from dotenv import load_dotenv

from agent_patrimonial.parametres import RACINE

# On lit le fichier .env de la racine du projet (s'il existe)
load_dotenv(RACINE / ".env")

OLLAMA_MODELE = os.getenv("OLLAMA_MODELE", "qwen2.5:3b")              # le modèle Qwen à utiliser
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")         # l'adresse du serveur Ollama
TEMPERATURE = float(os.getenv("TEMPERATURE", "0"))                     # 0 = des réponses stables