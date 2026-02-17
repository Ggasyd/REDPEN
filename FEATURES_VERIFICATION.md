# Vérification des fonctionnalités templates/zones + alignement + pipeline V2

Date: 2026-02-17

## Résumé

- ✅ **(1) Upload template (avec champ fichier dans `ExamTemplate`)**: **implémenté**.
- ✅ **(2) Extract auto + insert zones**: **implémenté**.
- ✅ **(3) GET preview zones**: **implémenté**.
- ✅ **(4) PATCH/PUT ajustement + validate**: **implémenté**.
- ✅ **(5) Audit/versioning**: **implémenté** (révisions créées lors des extractions et mises à jour de zones).

## Détails

### Templates/Zones (PR2)

- Upload template: `POST /api/exams/versions/{version_id}/templates`.
- Extraction + persistence zones: `POST /api/exams/templates/{template_id}/zones/extract`.
- Preview zones: `GET /api/exams/templates/{template_id}/zones`.
- Update zone unitaire: `PATCH/PUT /api/exams/templates/{template_id}/zones/{zone_id}`.
- Update zone batch: `PATCH /api/exams/templates/{template_id}/zones`.
- Validation globale: `POST /api/exams/templates/{template_id}/zones/validate`.
- Reset zones: `POST /api/exams/templates/{template_id}/zones/reset`.
- Révisions: création d’entrées `TemplateZoneRevision` sur extraction/update/validation.

### Alignement (PR3)

- Service: `backend/app/ml/alignment_service.py`.
- Stratégie: ORB primaire, fallback AKAZE, fallback final ECC.
- Rotations testées: `[0, 90, 180, 270]`.
- Métadonnées persistées sur `Submission`:
  - `alignment_score`,
  - `alignment_method`,
  - `alignment_rotation`.
- Observabilité:
  - logs structurés (keypoints, inliers, méthode retenue),
  - overlay debug optionnel (upload artifact).

### Pipeline V2 (PR4)

- Feature flag: `pipeline_v2_enabled` (config).
- Flux V2:
  1. chargement template actif,
  2. split pages,
  3. alignement page/template,
  4. OCR par zone (`extract_text_from_crop`),
  5. création `AnswerBlock` avec `question_key`.
- OCR par zone:
  - crop bbox,
  - prétraitement léger (grayscale + adaptive threshold),
  - détection zone vide via `ink_ratio` pour éviter OCR inutile.
- Matrice de statut:
  - `ERROR` si alignement impossible,
  - `PROCESSED` si seuils alignement/couverture satisfaits,
  - `NEEDS_REVIEW` sinon.
- Compatibilité descendante:
  - pipeline legacy conservé,
  - worker ne force `PROCESSED` que si le pipeline n’a pas déjà fixé un autre statut.

- Route API présente: `POST /api/exams/versions/{version_id}/templates`.
- Upload multipart (`UploadFile`), validations PDF/content-type, hash SHA-256, stockage, insertion `ExamTemplate`, activation optionnelle via `active_template_id`.
- Champs fichier (`original_filename`, `storage_url`, `content_type`, `file_size`) présents dans le modèle `ExamTemplate`.
- Tests unitaires présents pour succès + validation content-type.

### 2) Extract auto + insert zones

- Route API présente: `POST /api/exams/templates/{template_id}/zones/extract`.
- La route télécharge le PDF, appelle `extract_template_zones_from_pdf`, supprime les zones existantes, insère les nouvelles `TemplateZone`, met à jour `page_count` et crée une entrée de révision (`change_type="extract_insert"`) par zone.
- Test unitaire présent pour extraction + insertion persistée.

### 3) GET preview zones

- Route API présente: `GET /api/exams/templates/{template_id}/zones`.
- Retourne la liste des zones triées (`page_index`, `question_key`) au format `TemplateZoneResponse`.
- Test unitaire présent pour la récupération preview après extraction.

### 4) PATCH/PUT ajustement + validate

- Routes API présentes:
  - `PATCH /api/exams/templates/{template_id}/zones/{zone_id}`
  - `PUT /api/exams/templates/{template_id}/zones/{zone_id}` (alias de `PATCH`)
- Le patch gère les ajustements de bbox/champs de zone, la validation (`is_validated`, `validated_at`, `validated_by`) et les métadonnées d'édition (`last_edited_at`, `last_edited_by`, `edit_source`).
- En cas de changement, une révision est écrite (`change_type="update"`).
- Test unitaire présent sur mise à jour + validation + création de révision.


- Modèle `TemplateZoneRevision` présent et relié à `TemplateZone`.
- Fonction `_create_zone_revision(...)` implémentée pour incrémenter `revision_number` et persister un snapshot complet des données de zone.
- Cette fonction est appelée dans les workflows d'extraction (`extract_insert`) et de mise à jour (`update`), ce qui couvre l'audit/versioning applicatif.

Pour éviter les écarts de contexte (chemin ou env) sur la PR4, utiliser le script:

Les 5 fonctionnalités demandées sont bien implémentées côté API + modèle de données, avec des tests ciblés pour les cas critiques (upload, extract+preview, update+validate+revision).
