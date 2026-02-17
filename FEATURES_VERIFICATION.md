# Vérification des fonctionnalités templates/zones + alignement + pipeline V2

Date: 2026-02-17

## Résumé

- ✅ **(1) Upload template (avec champ fichier dans `ExamTemplate`)**: **implémenté**.
- ✅ **(2) Extract auto + insert zones**: **implémenté**.
- ✅ **(3) GET preview zones**: **implémenté**.
- ✅ **(4) PATCH/PUT ajustement + validate**: **implémenté**.
- ✅ **(5) Audit/versioning**: **implémenté** (révisions créées lors des extractions et mises à jour de zones).

## Détails

### 1) Upload template

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

### 5) Audit/versioning

- Modèle `TemplateZoneRevision` présent et relié à `TemplateZone`.
- Fonction `_create_zone_revision(...)` implémentée pour incrémenter `revision_number` et persister un snapshot complet des données de zone.
- Cette fonction est appelée dans les workflows d'extraction (`extract_insert`) et de mise à jour (`update`), ce qui couvre l'audit/versioning applicatif.

## Conclusion opérationnelle

Les 5 fonctionnalités demandées sont bien implémentées côté API + modèle de données, avec des tests ciblés pour les cas critiques (upload, extract+preview, update+validate+revision).
