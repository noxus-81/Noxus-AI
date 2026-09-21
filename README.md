# Mon Agent IA Local

Ce projet contient un agent IA autonome de base, conçu pour s'exécuter sur une Machine Virtuelle (VM) Windows.

## Comment l'installer sur votre Machine Virtuelle

1. **Copiez ce dossier** (`custom_agent`) sur votre Machine Virtuelle Windows.
2. **Installez Python** sur la VM si ce n'est pas déjà fait.
3. Ouvrez un terminal (PowerShell ou CMD) dans ce dossier.
4. **Installez les dépendances** :
   ```bash
   pip install -r requirements.txt
   ```
5. **Configurez l'API** :
   - Renommez le fichier `.env.example` en `.env`.
   - Ouvrez le fichier `.env` et remplacez `votre_cle_api_ici` par votre clé API Gemini (vous pouvez l'obtenir sur [Google AI Studio](https://aistudio.google.com/)).

## Comment le lancer

Exécutez le script avec Python :
```bash
python agent.py
```

L'agent va démarrer dans le terminal. Vous pouvez lui demander de faire ce que vous voulez. **Pour des raisons de sécurité, chaque commande générée par l'IA demandera votre validation (`o/n`) avant d'être exécutée.**
