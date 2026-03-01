# 🥤 WakAgenda – Backend

**Agenda interactif des stagiaires – Boissons du Cameroun (SABC)**  
Backend API REST · Python 3.12 · FastAPI · PostgreSQL · Clean Architecture · SOLID

---

## 📋 Table des matières

1. [Prérequis](#-prérequis)
2. [Structure du projet](#-structure-du-projet)
3. [Installation sur Windows](#-installation-sur-windows)
4. [Configuration](#-configuration)
5. [Lancer le serveur](#-lancer-le-serveur)
6. [Base de données & Migrations](#-base-de-données--migrations)
7. [Documentation de l'API](#-documentation-de-lapi)
8. [Lancer avec Docker](#-lancer-avec-docker)
9. [Tests](#-tests)
10. [Architecture & Design](#-architecture--design)
11. [Routes disponibles](#-routes-disponibles)
12. [Dépannage](#-dépannage)

---

## 🔧 Prérequis

Installez ces logiciels **dans l'ordre** avant de commencer :

| Logiciel | Version | Lien |
|---|---|---|
| Python | 3.12 | https://www.python.org/downloads/ |
| PostgreSQL | 16 | https://www.postgresql.org/download/windows/ |
| Git | 2.x | https://git-scm.com/download/win |
| Docker Desktop *(optionnel)* | 24.x | https://www.docker.com/products/docker-desktop/ |

> **Important Python** : Lors de l'installation, cochez ✅ **"Add Python to PATH"**

---

## 📁 Structure du projet

```
wakagenda-backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── auth.py          # POST /register, POST /login
│   │       │   ├── users.py         # GET /me, GET /{id}, PATCH /me, ...
│   │       │   ├── tasks.py         # CRUD tâches + stats + calendrier
│   │       │   ├── notifications.py # GET, PATCH /read, DELETE
│   │       │   └── reports.py       # GET /pdf
│   │       └── router.py
│   │   └── deps.py                  # Dépendance JWT get_current_user
│   ├── core/
│   │   ├── config.py                # Configuration pydantic-settings
│   │   ├── security.py              # bcrypt + JWT
│   │   └── exceptions.py           # Exceptions HTTP métier
│   ├── db/
│   │   ├── base_class.py            # DeclarativeBase SQLAlchemy
│   │   ├── base.py                  # Import models pour Alembic
│   │   └── session.py               # Engine + get_db()
│   ├── models/                      # Modèles SQLAlchemy (tables DB)
│   │   ├── user.py
│   │   ├── task.py
│   │   └── notification.py
│   ├── repositories/                # Couche accès données (Repository Pattern)
│   │   ├── user_repository.py
│   │   ├── task_repository.py
│   │   └── notification_repository.py
│   ├── schemas/                     # Schémas Pydantic (validation I/O)
│   │   ├── user.py
│   │   ├── auth.py
│   │   ├── task.py
│   │   └── notification.py
│   ├── services/                    # Logique métier
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── task_service.py
│   │   ├── notification_service.py
│   │   └── report_service.py        # Génération PDF ReportLab
│   └── main.py                      # Point d'entrée FastAPI
├── alembic/                         # Migrations DB
├── tests/                           # Tests pytest
├── requirements.txt
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── .env.example
└── README.md
```

---

## 💻 Installation sur Windows

### Étape 1 – Cloner ou extraire le projet

```cmd
cd C:\Users\VotreNom\Documents
git clone <url-du-repo> wakagenda-backend
cd wakagenda-backend
```

---

### Étape 2 – Créer l'environnement virtuel Python

Ouvrez **l'Invite de commandes** (CMD) ou **PowerShell** en tant qu'administrateur :

```cmd
cd C:\Users\VotreNom\Documents\wakagenda-backend

python -m venv venv
```

Activez l'environnement :

```cmd
# CMD (Invite de commandes classique)
venv\Scripts\activate.bat

# PowerShell
venv\Scripts\Activate.ps1
```

> **Note PowerShell** : si vous obtenez une erreur de politique d'exécution, lancez d'abord :
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

Vous devriez voir `(venv)` au début de votre ligne de commande.

---

### Étape 3 – Installer les dépendances Python

```cmd
pip install -r requirements.txt
```

L'installation prend environ 1-2 minutes. Attendez le message `Successfully installed`.

---

### Étape 4 – Configurer PostgreSQL

#### 4a – Créer la base de données

Ouvrez **pgAdmin** (installé avec PostgreSQL) ou utilisez `psql` :

```cmd
# Ouvrir psql (remplacez le chemin si nécessaire)
"C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres
```

Dans le shell psql, tapez ces commandes :

```sql
-- Créer l'utilisateur
CREATE USER wakagenda_user WITH PASSWORD 'wakagenda_pass';

-- Créer la base de données
CREATE DATABASE wakagenda_db OWNER wakagenda_user;

-- Donner tous les droits
GRANT ALL PRIVILEGES ON DATABASE wakagenda_db TO wakagenda_user;

-- Quitter
\q
```

#### 4b – Vérifier la connexion

```cmd
"C:\Program Files\PostgreSQL\16\bin\psql.exe" -U wakagenda_user -d wakagenda_db -c "SELECT version();"
```

Si vous voyez la version de PostgreSQL, la connexion fonctionne ✅

---

### Étape 5 – Créer le fichier de configuration `.env`

Dans le dossier `wakagenda-backend`, copiez le fichier exemple :

```cmd
copy .env.example .env
```

Ouvrez `.env` avec le Bloc-notes ou VS Code et modifiez si nécessaire :

```env
# Obligatoire : changer cette clé secrète en production !
SECRET_KEY=wakagenda-sabc-secret-key-2026-changez-en-prod

DATABASE_URL=postgresql://wakagenda_user:wakagenda_pass@localhost:5432/wakagenda_db

ALLOWED_ORIGINS=http://localhost:3000

DEBUG=True
```

> ⚠️ Ne committez **jamais** le fichier `.env` sur Git.

---

## ▶️ Lancer le serveur

### Option A – Développement (recommandé)

Avec l'environnement virtuel activé :

```cmd
# Appliquer les migrations (créer les tables)
alembic upgrade head

# Lancer le serveur avec rechargement automatique
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Résultat attendu :
```
✅  WakAgenda v1.0.0 démarré en mode DEBUG.
📄  Documentation Swagger : http://127.0.0.1:8000/docs
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Option B – Sans rechargement automatique (production locale)

```cmd
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

---

## 🗄️ Base de données & Migrations

### Première initialisation

```cmd
# Créer la migration initiale (si pas encore faite)
alembic revision --autogenerate -m "Initial migration"

# Appliquer les migrations
alembic upgrade head
```

### Après modification d'un modèle

```cmd
alembic revision --autogenerate -m "Description du changement"
alembic upgrade head
```

### Annuler la dernière migration

```cmd
alembic downgrade -1
```

### Voir l'historique

```cmd
alembic history
alembic current
```

---

## 📖 Documentation de l'API

Une fois le serveur démarré, accédez à :

| Interface | URL | Description |
|---|---|---|
| **Swagger UI** | http://127.0.0.1:8000/docs | Interface interactive, test des routes |
| **ReDoc** | http://127.0.0.1:8000/redoc | Documentation lisible |
| **OpenAPI JSON** | http://127.0.0.1:8000/openapi.json | Schéma brut |
| **Health Check** | http://127.0.0.1:8000/health | État du serveur |

---

## 🐳 Lancer avec Docker

Si Docker Desktop est installé et en cours d'exécution :

```cmd
# Construire et démarrer tous les services (PostgreSQL + Backend)
docker-compose up --build

# En arrière-plan
docker-compose up --build -d

# Voir les logs
docker-compose logs -f backend

# Arrêter
docker-compose down

# Arrêter et supprimer les volumes (reset DB)
docker-compose down -v
```

> Avec Docker, vous n'avez **pas besoin** d'installer PostgreSQL séparément.

---

## 🧪 Tests

```cmd
# Activer l'environnement virtuel si ce n'est pas fait
venv\Scripts\activate.bat

# Lancer tous les tests
pytest tests/ -v

# Avec couverture de code
pytest tests/ -v --cov=app --cov-report=html

# Ouvrir le rapport de couverture
start htmlcov\index.html
```

---

## 🏗️ Architecture & Design

### Clean Architecture

```
┌─────────────────────────────────────────┐
│           API (Endpoints FastAPI)        │  ← Présentation
├─────────────────────────────────────────┤
│           Services (Logique métier)      │  ← Application
├─────────────────────────────────────────┤
│        Repositories (Accès données)     │  ← Infrastructure
├─────────────────────────────────────────┤
│         Models SQLAlchemy (DB)          │  ← Infrastructure
└─────────────────────────────────────────┘
```

### Principes SOLID appliqués

| Principe | Application |
|---|---|
| **S** – Single Responsibility | Chaque classe a un seul rôle : config, sécurité, repository, service |
| **O** – Open/Closed | Les exceptions étendent `HTTPException` sans la modifier |
| **L** – Liskov Substitution | Les repositories sont interchangeables via leurs interfaces |
| **I** – Interface Segregation | Schemas séparés : `UserCreate`, `UserUpdate`, `UserResponse` |
| **D** – Dependency Inversion | Les services dépendent des repositories injectés, pas des implémentations |

### Flux d'une requête

```
Client → Endpoint → Dépendance JWT → Service → Repository → DB
                                        ↓
                                   Schéma Pydantic
                                        ↓
                                   Response JSON
```

---

## 🛣️ Routes disponibles

### 🔐 Authentification
| Méthode | Route | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Onboarding – créer un compte |
| `POST` | `/api/v1/auth/login` | Connexion – obtenir un JWT |

### 👤 Utilisateurs
| Méthode | Route | Description |
|---|---|---|
| `GET` | `/api/v1/users/me` | Profil de l'utilisateur connecté |
| `GET` | `/api/v1/users/{user_id}` | Profil par ID |
| `PATCH` | `/api/v1/users/me` | Modifier son profil |
| `POST` | `/api/v1/users/me/picture` | Uploader une photo de profil |
| `DELETE` | `/api/v1/users/me` | Supprimer son compte |

### 📋 Tâches & Événements
| Méthode | Route | Description |
|---|---|---|
| `POST` | `/api/v1/tasks` | Créer une tâche |
| `GET` | `/api/v1/tasks` | Lister (avec filtres : catégorie, domaine, statut, dates) |
| `GET` | `/api/v1/tasks/today` | Tâches du jour |
| `GET` | `/api/v1/tasks/upcoming` | Prochaines tâches |
| `GET` | `/api/v1/tasks/stats` | Statistiques dashboard |
| `GET` | `/api/v1/tasks/{task_id}` | Détail d'une tâche |
| `PATCH` | `/api/v1/tasks/{task_id}` | Modifier une tâche |
| `DELETE` | `/api/v1/tasks/{task_id}` | Supprimer une tâche |

### 🔔 Notifications
| Méthode | Route | Description |
|---|---|---|
| `GET` | `/api/v1/notifications` | Toutes les notifications |
| `GET` | `/api/v1/notifications/unread` | Non lues seulement |
| `GET` | `/api/v1/notifications/unread/count` | Badge compteur |
| `PATCH` | `/api/v1/notifications/{id}/read` | Marquer comme lue |
| `PATCH` | `/api/v1/notifications/read-all` | Tout marquer comme lu |
| `DELETE` | `/api/v1/notifications/{id}` | Supprimer |

### 📄 Rapport PDF
| Méthode | Route | Description |
|---|---|---|
| `GET` | `/api/v1/reports/pdf` | Générer et télécharger le rapport PDF |

**Paramètres optionnels du rapport** :
- `date_from` : Date de début `YYYY-MM-DD` (défaut : début du stage)
- `date_to` : Date de fin `YYYY-MM-DD` (défaut : aujourd'hui)

Exemple : `GET /api/v1/reports/pdf?date_from=2026-02-01&date_to=2026-02-28`

---

## 🔑 Utiliser l'API avec Postman

### 1. S'inscrire (onboarding)
```
POST http://127.0.0.1:8000/api/v1/auth/register
Content-Type: application/json

{
  "email": "gabrielle@sabc.cm",
  "password": "MonMotDePasse123",
  "first_name": "Gabrielle",
  "last_name": "Nguetcho",
  "department": "DSI – Transformation Digitale",
  "supervisor_name": "M. William Olivier FOSSO",
  "internship_start_date": "2026-01-15"
}
```

### 2. Se connecter
```
POST http://127.0.0.1:8000/api/v1/auth/login
Content-Type: application/json

{
  "email": "gabrielle@sabc.cm",
  "password": "MonMotDePasse123"
}
```

### 3. Utiliser le token
Copiez le champ `access_token` de la réponse et ajoutez-le dans l'en-tête :
```
Authorization: Bearer <votre_token_ici>
```

### 4. Créer une tâche
```
POST http://127.0.0.1:8000/api/v1/tasks
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Réunion de suivi DSI",
  "task_date": "2026-02-25",
  "start_time": "09:00",
  "end_time": "10:00",
  "category": "Réunion",
  "domain": "Technique",
  "status": "À faire",
  "reminder": "15 min avant",
  "notification_enabled": true,
  "description": "Réunion hebdomadaire avec l'équipe DSI"
}
```

### 5. Télécharger le rapport PDF
Ouvrez dans le navigateur ou Postman :
```
GET http://127.0.0.1:8000/api/v1/reports/pdf
Authorization: Bearer <token>
```

---

## 🚨 Dépannage

### ❌ `ModuleNotFoundError: No module named 'app'`

Vous devez être dans le dossier racine du projet :
```cmd
cd C:\Users\VotreNom\Documents\wakagenda-backend
venv\Scripts\activate.bat
uvicorn app.main:app --reload
```

### ❌ `could not connect to server: Connection refused` (PostgreSQL)

Vérifiez que PostgreSQL est démarré :
```cmd
# Dans les Services Windows (services.msc)
# Cherchez "postgresql-x64-16" et démarrez le service

# Ou via la commande
net start postgresql-x64-16
```

### ❌ `password authentication failed for user "wakagenda_user"`

Recréez l'utilisateur :
```cmd
"C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres
```
```sql
DROP USER IF EXISTS wakagenda_user;
CREATE USER wakagenda_user WITH PASSWORD 'wakagenda_pass';
GRANT ALL PRIVILEGES ON DATABASE wakagenda_db TO wakagenda_user;
\q
```

### ❌ PowerShell bloque l'activation du venv

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
venv\Scripts\Activate.ps1
```

### ❌ `alembic: command not found`

```cmd
venv\Scripts\activate.bat
pip install alembic
```

### ❌ Erreur `CORS` depuis le frontend

Modifiez `.env` :
```env
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```
Redémarrez le serveur.

---

## 📞 Contact & Supervision

- **Réalisé par** : NGUETCHO BIADOU Chloé Gabrielle – Stagiaire DSI
- **Superviseur** : M. William Olivier FOSSO – Architecte Logiciel, DSI
- **Entité** : Direction des Systèmes d'Information – Boissons du Cameroun
- **Version** : 1.0 | **Date** : 24 février 2026

---

*WakAgenda – Agenda interactif des stagiaires · Boissons du Cameroun © 2026*
