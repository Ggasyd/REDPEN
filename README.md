# REDPEN
Correction de copies augmentées par IA

## 🎯 Vue d'ensemble

**REDPEN** est une solution SaaS de correction assistée par IA pour copies manuscrites (PDF/images). L'objectif clé est de supprimer le déchiffrage fastidieux tout en conservant la décision pédagogique humaine.

### Caractéristiques principales

- ✅ **Multi-tenant** : Support de workspaces personnels et d'établissement
- 🤖 **3 Piliers IA** : Géométrique (OCR), Sémantique (Vision), Détection (MCQ/tableaux)
- 📝 **Pipeline complet** : Upload → Extraction → OCR → Classification → Correction → Export
- 🔒 **GDPR Compliant** : Rétention automatique, anonymisation, suppression
- 📊 **Apprentissage supervisé** : Feedback humain pour amélioration continue
- 🚀 **Async Processing** : Celery + Redis pour traitement haute performance
- 🐳 **Production-ready** : Docker, CI/CD, tests exhaustifs

---

## 🏗️ Architecture

### Stack Technique

- **Backend** : Python 3.12 + FastAPI + Pydantic v2
- **Database** : PostgreSQL 16 + SQLAlchemy 2.0 + Alembic
- **Cache & Queue** : Redis + Celery
- **Storage** : MinIO (dev) / S3 (prod)
- **Auth** : JWT (access + refresh) + Argon2
- **AI/ML** :
  - Mistral OCR (Pixtral-12B) pour OCR/layout
  - GPT-4o-mini (vision) pour classification sémantique
  - Gemini 1.5 Flash en fallback
- **Tests** : pytest + httpx AsyncClient (90% coverage)
- **CI/CD** : GitHub Actions (lint, tests, build, security scan)

### Architecture 3 Piliers

#### 1. Pilier Géométrique (Copies structurées)
- OCR Mistral pour découpe horizontale entre questions
- Extraction complète du contenu (imprimé + manuscrit)
- Garantit le contexte pour phrases à trous

#### 2. Pilier Sémantique (Copies libres)
- Modèle vision (Gemini/GPT-4o-mini) pour classification
- Identification des paragraphes par sens, même non numérotés
- Jamais de correction, seulement classification + confidence

#### 3. Pilier Détection (QCM & tableaux)
- Analyse densité pixels / lettres isolées
- Déterministe et explicable
- Pas de LLM requis

---

## 🚀 Quick Start

### Prérequis

- Docker & Docker Compose
- Make (optionnel mais recommandé)

### Installation

```bash
# Cloner le repo
git clone <repository-url>
cd redpen

# Copier les variables d'environnement
cp backend/.env.example backend/.env

# Éditer backend/.env avec vos clés API
# - OPENAI_API_KEY
# - GOOGLE_API_KEY
# - MISTRAL_API_KEY

# Build et lancer les services
make build
make up

# Attendre que les services démarrent (5-10 sec)
# Créer les tables de la base de données
make migrate

# Seed avec données de démo
make seed
```

### Accès aux services

- **API** : http://localhost:8000
- **API Docs (Swagger)** : http://localhost:8000/docs
- **MinIO Console** : http://localhost:9001 (user: `redpen_minio`, pass: `redpen_minio_secret_key_123`)
- **Flower (Celery Monitor)** : http://localhost:5555

### Compte démo

Après le seed :
- **Email** : prof@redpen.fr
- **Password** : password123

---

## 📚 API Documentation

### Authentification

```bash
# Inscription
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "prof@example.com",
    "password": "password123",
    "full_name": "Professeur Test"
  }'

# Connexion
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "prof@redpen.fr",
    "password": "password123"
  }'
```

### Endpoints principaux

#### Workspaces
- `GET /api/workspaces/` - Liste des workspaces
- `POST /api/workspaces/` - Créer un workspace

#### Classrooms & Students
- `POST /api/classrooms/` - Créer une classe
- `POST /api/classrooms/{id}/students/import` - Importer élèves (CSV/Excel/PDF)
- `GET /api/classrooms/{id}/students` - Liste des élèves

#### Exams
- `POST /api/exams/` - Créer un examen
- `POST /api/exams/{id}/versions` - Créer une version
- `POST /api/exam_versions/{id}/questions` - Ajouter questions (bulk)

#### Submissions
- `POST /api/submissions/` - Upload copie (PDF/image)
- `GET /api/submissions/{id}` - Détails de la copie
- `GET /api/submissions/{id}/processing_status` - Statut de traitement
- `POST /api/submissions/{id}/reprocess` - Re-traiter

#### Review & Correction
- `GET /api/review/submissions/{id}/answer_blocks` - Blocs de réponses
- `PATCH /api/review/answer_blocks/{id}` - Modifier transcription/question
- `PATCH /api/review/grade_decisions/{id}` - Modifier note
- `POST /api/review/submissions/{id}/finalize` - Finaliser (verrouiller)

#### GDPR
- `GET /api/gdpr/settings/retention` - Paramètres de rétention
- `PATCH /api/gdpr/settings/retention` - Modifier paramètres (OWNER)
- `POST /api/gdpr/retention/run` - Lancer rétention (preview/anonymize/delete)
- `POST /api/gdpr/student/{id}/anonymize` - Anonymiser un élève

#### ML Datasets
- `GET /api/ml/datasets/supervised` - Export données supervisées
- `GET /api/ml/datasets/preferences` - Export préférences
- `GET /api/ml/calibration/metrics` - Métriques de calibration

---

## 🧪 Tests

```bash
# Lancer tous les tests
make test

# Tests avec couverture
make test-cov

# Linting
make lint

# Formatage
make format
```

### Couverture actuelle

- **Objectif** : 90%
- **Tests** : Auth, Multi-tenant, Workspaces, Classrooms, Exams, Submissions, GDPR
- **CI/CD** : Intégration GitHub Actions

---

## 🔧 Développement

### Commandes Make

```bash
make help          # Afficher toutes les commandes
make build         # Build Docker images
make up            # Démarrer tous les services
make down          # Arrêter tous les services
make logs          # Voir les logs
make migrate       # Appliquer migrations
make makemigrations # Créer nouvelle migration
make seed          # Seed données démo
make test          # Lancer tests
make test-cov      # Tests + couverture
make lint          # Linter le code
make format        # Formater le code
make clean         # Nettoyer containers + volumes
make shell         # Shell dans le container API
make psql          # Shell PostgreSQL
```

### Structure du projet

```
/app/
├── backend/
│   ├── app/
│   │   ├── models/          # Modèles SQLAlchemy
│   │   ├── schemas/         # Schémas Pydantic
│   │   ├── api/             # Routes API
│   │   ├── services/        # Logique métier
│   │   ├── workers/         # Tâches Celery
│   │   ├── ml/              # Services IA
│   │   ├── utils/           # Utilitaires
│   │   ├── config.py        # Configuration
│   │   ├── database.py      # Base de données
│   │   ├── main.py          # Application FastAPI
│   │   └── seed.py          # Données de démo
│   ├── tests/               # Tests
│   ├── alembic/             # Migrations
│   ├── requirements.txt     # Dépendances Python
│   ├── Dockerfile           # Image Docker
│   └── .env                 # Variables d'environnement
├── docker-compose.yml       # Services Docker
├── .github/workflows/       # CI/CD
├── Makefile                 # Commandes dev
└── README.md                # Ce fichier
```

---

## 🔐 Sécurité & GDPR

### Authentification
- JWT avec access + refresh tokens
- Hash de mot de passe Argon2
- Tokens expirables (30 min access, 7 jours refresh)

### GDPR
- **Rétention automatique** : Jobs Celery Beat quotidiens
- **Anonymisation** : PII supprimées, dissociation élèves
- **Suppression** : Hard delete après échéance
- **Mode EU ONLY** : Désactive IA US si activé
- **Pseudonymisation** : Données envoyées aux IA

### Paramètres de rétention par défaut
- Submissions : 730 jours (2 ans)
- Artifacts : 365 jours (1 an)
- ML Datasets : 365 jours (1 an)

---

## 🤖 Services IA

### Mistral OCR (Pixtral-12B)
- **Usage** : OCR + layout analysis
- **Endpoint** : https://api.mistral.ai/v1/chat/completions
- **Modèle** : pixtral-12b-2409
- **Coût** : Variable selon volume

### GPT-4o-mini (OpenAI)
- **Usage** : Classification sémantique (pilier 2)
- **Modèle** : gpt-4o-mini
- **Fallback** : Gemini 1.5 Flash

### Gemini 1.5 Flash (Google)
- **Usage** : Fallback classification sémantique
- **Modèle** : gemini-1.5-flash
- **API** : google-generativeai

---

## 📊 Pipeline de traitement

```
1. Upload PDF/Image
   ↓
2. Split pages (PyPDF2 + pdf2image)
   ↓
3. Pour chaque page :
   ├─ Pilier Géométrique : OCR Mistral → découpage horizontal
   ├─ Pilier Sémantique : GPT-4o-mini → classification par sens
   └─ Pilier Détection : Analyse pixels → MCQ/tableaux
   ↓
4. OCR/HTR verbatim (transcription stricte)
   ↓
5. Assignation question (AI + confidence)
   ↓
6. Assignation élève (hiérarchique) :
   ├─ 1. Explicite (student_id fourni)
   ├─ 2. OCR zone nom + fuzzy matching
   ├─ 3. Suggestion IA (jamais auto-validé)
   └─ 4. Validation humaine
   ↓
7. Génération proposition note + justification
   ↓
8. Flags NEEDS_REVIEW si confidence < seuil
   ↓
9. Correction augmentée (interface humaine)
   ↓
10. Finalisation + Export PDF annoté
```

---

## 🌐 Déploiement

### Docker Compose (Production)

```bash
# Éditer docker-compose.yml pour production
# - Changer ENVIRONMENT=production
# - Configurer S3 au lieu de MinIO
# - Activer HTTPS
# - Configurer secrets

docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes (optionnel)

Des manifests Kubernetes peuvent être générés pour un déploiement scalable :
- Deployment API + Worker
- Services (ClusterIP, LoadBalancer)
- Ingress (Nginx/Traefik)
- Secrets pour clés API
- PersistentVolumeClaims pour storage

---

## 🤝 Contribution

1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/amazing-feature`)
3. Commit les changements (`git commit -m 'Add amazing feature'`)
4. Push vers la branche (`git push origin feature/amazing-feature`)
5. Ouvrir une Pull Request

### Standards de code

- **Formatage** : Black (line-length=100)
- **Linting** : Ruff
- **Type hints** : Obligatoire (mypy)
- **Docstrings** : Google style
- **Tests** : Coverage minimum 80%

---

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

---

## 📧 Support

Pour toute question ou problème :
- **Issues** : [GitHub Issues](https://github.com/redpen/redpen/issues)
- **Email** : support@redpen.fr

---

## 🙏 Remerciements

- **Mistral AI** pour l'OCR Pixtral
- **OpenAI** pour GPT-4o-mini
- **Google** pour Gemini 1.5 Flash
- **FastAPI** pour le framework
- **PostgreSQL** pour la base de données
- **Celery** pour le traitement asynchrone

---

**Made with ❤️ for teachers who want to focus on pedagogy, not deciphering!**

