# Booking Scraper

Scraper Scrapy ciblant Booking.com pour récupérer les meilleurs hôtels d'une liste de villes.

## Prérequis

Deux options possibles :

- **Utilisation indépendante** : Python 3.10+ et les dépendances suivantes :

  ```bash
  pip install scrapy python-dotenv
  ```

- **Utilisation dans le cadre du projet Kayak** : les prérequis du projet Kayak suffisent (Scrapy et python-dotenv sont déjà inclus).

## Configuration

Un token AWS WAF valide, récupéré depuis une session navigateur sur booking.com, doit être défini via la variable d'environnement `AWS_WAF_TOKEN` dans un fichier `.env` :

- **Utilisation indépendante** : créer le fichier `.env` à la racine du projet (au même niveau que `scrapy.cfg`).
- **Utilisation dans le cadre du projet Kayak** : utiliser le fichier `.env` du projet Kayak, situé un niveau plus haut que ce dossier.

Contenu attendu du `.env` :

```env
AWS_WAF_TOKEN=votre_token_ici
```

> Ce token a une durée de vie limitée et doit être renouvelé manuellement lorsqu'il expire.

## Fichier CSV d'entrée

Le scraper attend un fichier CSV **avec `;` comme séparateur** et les trois colonnes suivantes dans cet ordre :

| Colonne     | Description                          |
|-------------|--------------------------------------|
| `city_id`   | Identifiant unique de la ville       |
| `city_name` | Nom de la ville (utilisé en requête) |
| `city_rank` | Rang de la ville (non utilisé)       |

Exemple (`cities.csv`) :

```csv
city_id;city_name;city_rank
1;Paris;1
2;Lyon;2
3;Marseille;3
```

## Exécution

Depuis la racine du projet :

```bash
scrapy crawl booking -a cities_csv=cities.csv -O output.json
```

- `-a cities_csv=...` : chemin vers le fichier CSV des villes.
- `-O output.json` : fichier JSON de sortie (écrase le fichier s'il existe ; utiliser `-o` pour ajouter à un fichier existant).

## Sortie

Le fichier JSON produit contient, pour chaque hôtel, les champs suivants :

- `city_id`
- `name`
- `address`
- `note`
- `url`
- `description`
- `latitude`
- `longitude`