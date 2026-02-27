# YGGTorznab

Torznab API server for YGG Torrent. Permet d'utiliser YGG avec Sonarr, Radarr, Prowlarr, etc.

> **Note** : Conçu pour les utilisateurs **non-boost** de YGG. Utilise Selenium pour naviguer sur le site comme un utilisateur classique (pas d'accès API réservé aux comptes boost).

## Prérequis

- Docker & Docker Compose
- Un compte YGG Torrent
- (Optionnel) Une clé API [TMDB](https://www.themoviedb.org/) pour la recherche par IMDb/TMDB/TVDb ID

## Installation

```bash
git clone <repo-url> && cd yggtzn
cp .env.example .env
```

Éditer `.env` avec vos identifiants :

```env
YGG_USERNAME=votre_username
YGG_PASSWORD=votre_password
API_KEY=votre_api_key
TMDB_API_KEY=votre_cle_tmdb
```

## Lancement

```bash
docker compose up -d --build
```

Le service est accessible sur `http://localhost:7474`.

## Configuration

| Variable | Description | Défaut |
|---|---|---|
| `YGG_USERNAME` | Identifiant YGG | |
| `YGG_PASSWORD` | Mot de passe YGG | |
| `API_KEY` | Clé d'authentification API | `changeme` |
| `HEADLESS` | Mode headless du navigateur | `true` |
| `MAX_SEARCH_PAGES` | Pages de résultats max | `3` |
| `TMDB_API_KEY` | Clé API TMDB | |
| `DEBUG` | Logs de debug | `false` |

## Utilisation avec Sonarr / Radarr / Prowlarr

Dans Prowlarr, ajouter un indexeur de type **Generic Torznab** avec :

- **URL** : `http://<host>:7474`
- **API Path** : `/api`
- **API Key** : la valeur de `API_KEY` dans `.env`

## Endpoints

| Route | Description |
|---|---|
| `GET /api?t=caps&apikey=...` | Capacités de l'indexeur |
| `GET /api?t=search&q=...&apikey=...` | Recherche par texte |
| `GET /api?t=tvsearch&q=...&apikey=...` | Recherche série TV |
| `GET /api?t=movie&q=...&apikey=...` | Recherche film |
| `GET /download?url=...&apikey=...` | Télécharger un torrent |

## Sans Docker

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
python main.py
```

> Nécessite Google Chrome installé sur la machine.
