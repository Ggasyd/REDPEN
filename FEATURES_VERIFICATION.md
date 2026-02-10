# Vérification des 5 fonctionnalités templates/zones

Date: 2026-02-10

## Résumé

- ✅ **(1) Upload template (avec champ fichier dans `ExamTemplate`)**: **implémenté**.
- ⚠️ **(2) Extract auto + insert zones**: **partiellement implémenté** (extraction utilitaire présente, mais pas branchée à un endpoint/workflow persistant).
- ❌ **(3) GET preview zones**: **non implémenté** (aucune route dédiée détectée).
- ❌ **(4) PATCH/PUT ajustement + validate**: **non implémenté côté API** (modèle DB prêt mais pas d'endpoint).
- ⚠️ **(5) Audit/versioning**: **partiellement implémenté** (tables/modèles présents, pas de logique applicative trouvée pour écrire les révisions).

## Détails

### 1) Upload template

- Route API présente: `POST /api/exams/versions/{version_id}/templates`.
- Upload multipart (`UploadFile`), validations PDF/content-type, hash SHA-256, stockage, insertion `ExamTemplate`, activation optionnelle via `active_template_id`.
- Champs fichier (`original_filename`, `storage_url`, `content_type`, `file_size`) présents dans le modèle `ExamTemplate`.
- Tests unitaires présents pour succès + validation content-type.

### 2) Extract auto + insert zones

- Fonction d'extraction PDF disponible (`extract_template_zones_from_pdf`) via PyMuPDF.
- **Aucun appel** détecté vers cette fonction dans les routes/services.
- Conclusion: extraction candidate existe mais **pas intégrée** à un flux complet "extract + insert zones".

### 3) GET preview zones

- Aucune route `/zones` ou `/preview` liée aux templates/zones détectée dans l'API examens.
- Le seul `preview` détecté est côté GDPR retention mode, non lié aux zones de template.

### 4) PATCH/PUT ajustement + validate

- Champs de validation/édition existent dans `TemplateZone` (`is_validated`, `validated_at`, `validated_by`, `last_edited_*`, `edit_source`).
- Mais aucune route `PATCH`/`PUT` dédiée aux zones détectée dans l'API.

### 5) Audit/versioning

- Modèle `TemplateZoneRevision` + migration DB de création de table présents.
- **Pas de logique applicative trouvée** (service/router) qui crée des lignes de révision lors d'éditions/validations.

## Conclusion opérationnelle

Le socle data est avancé (templates, zones, validation, révisions), mais l'API métier autour des zones est incomplète. En l'état:

- prêt pour upload template,
- non prêt pour un workflow complet de zones (auto-extract persisté, preview, ajustement/validation, audit effectif).
