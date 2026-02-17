# Vérification des fonctionnalités templates/zones + alignement + pipeline V2

Date: 2026-02-17

## Résumé

- ✅ **(1) Upload template (lié à `exam_version`)**: implémenté.
- ✅ **(2) Extraction auto + insertion des zones**: implémenté (`/templates/{id}/zones/extract`) avec metadata extracteur.
- ✅ **(3) Preview zones**: implémenté (`GET /templates/{id}/zones`) avec champs d’audit.
- ✅ **(4) Ajustement manuel + validation**: implémenté (PATCH/PUT zone, bulk PATCH, validate global, reset).
- ✅ **(5) Audit/versioning des zones**: implémenté via `TemplateZoneRevision`.
- ✅ **(6) Service alignement PR3**: implémenté (ORB + fallback AKAZE/ECC + rotation + score + observabilité).
- ✅ **(7) Pipeline V2 PR4 (feature-flagged)**: implémenté (template → alignement → zones → OCR par zone + matrice de statut).

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

## Conclusion opérationnelle

Le socle template/zone + alignement + pipeline V2 est désormais en place côté backend, avec rollback via feature flag et observabilité alignement.
