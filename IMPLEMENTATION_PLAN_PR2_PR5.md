# Plan d'implémentation PR2 → PR5 (Template, Alignement, Pipeline V2, Tests)

## 1) État actuel de la base (diagnostic rapide)

### Ce qui existe déjà et peut être réutilisé
- **Modèles template/zones** déjà en place : `ExamTemplate`, `TemplateZone`, `TemplateZoneRevision` avec validation et historique.
- **Endpoints templates** déjà partiellement implémentés : upload PDF, extraction de zones, preview de zones, patch/put d'ajustement des zones.
- **Extraction zones** existante via `PyMuPDF` (`extract_template_zones_from_pdf`) avec détection naïve des labels de questions.
- **Champs d’alignement** présents dans `Submission` : `alignment_score`, `alignment_method`, `alignment_rotation`.
- **Pipeline existant** (`app/ml/pipeline.py`) encore orienté “3 piliers” et non “template-first”.

### Gaps principaux par rapport aux PR demandées
- **PR2** : endpoints présents mais il manque une séparation claire entre “proposition auto” et “validation finale”, et des garde-fous métier (zones actives/validées pour production).
- **PR3** : service d’alignement absent (ORB/AKAZE/ECC + rotation + score) malgré les champs DB.
- **PR4** : pipeline V2 (template → alignement → zones → OCR par zone) absent ; le pipeline actuel est générique et non piloté par template.
- **PR5** : tests ciblés (extraction, alignement, OCR par zone, e2e pipeline V2) à compléter ; l’existant couvre surtout l’API template de base.

---

## 2) Plan d’implémentation étape par étape

## PR2 — Endpoints template

### Étape PR2.1 — Contract API (stabiliser les flux)
1. **Conserver** les endpoints déjà existants pour :
   - upload template PDF,
   - extraction zones,
   - preview zones,
   - ajustement manuel des zones.
2. **Ajouter un endpoint de validation globale** (ex: `POST /templates/{id}/zones/validate`) qui :
   - vérifie cohérence des zones (bbox > 0, page_index valide),
   - marque les zones comme validées,
   - met un statut template (`metadata_json.status = zones_validated`).
3. **Ajouter un endpoint de reset/re-extract** (optionnel mais recommandé) pour retravailler un template sans recréer toute la version.

### Étape PR2.2 — Fiabiliser l’extraction PyMuPDF
1. Étendre `extract_template_zones_from_pdf` :
   - tri déterministe des blocs,
   - déduplication de labels `Qx`,
   - heuristique de bbox “zone de réponse” (pas seulement bbox du label).
2. Ajouter dans `metadata_json` des métriques : nb zones détectées, nb pages, version heuristique.
3. Préparer la compatibilité avec un futur mode mixte (vectoriel + OCR fallback).

### Étape PR2.3 — UX Preview (backend contract)
1. Exposer les zones avec attributs nécessaires au front : `is_validated`, `edit_source`, `confidence`, horodatages.
2. Autoriser la mise à jour batch des zones (endpoint bulk PATCH) pour éviter N requêtes front.
3. Journaliser chaque changement via `TemplateZoneRevision` (déjà présent) en ajoutant un `change_reason` standardisé.

---

## PR3 — Service alignement

### Étape PR3.1 — Créer le module d’alignement
1. Créer `backend/app/ml/alignment_service.py`.
2. API interne proposée :
   - `align_to_template(submission_page_bytes, template_page_bytes) -> AlignmentResult`
   - `AlignmentResult = {aligned_image_bytes, method, score, rotation, homography_meta}`

### Étape PR3.2 — Implémenter la stratégie ORB + fallback
1. **Phase A (primaire)** : ORB + BFMatcher + homographie RANSAC.
2. **Phase B (fallback)** : AKAZE si ORB échoue (peu de points/matches).
3. **Phase C (fallback final)** : ECC (corrélation) pour cas faible texture.
4. Définir des seuils explicites de succès/échec et un score normalisé [0,1].

### Étape PR3.3 — Gestion rotation 90/180
1. Tester orientations `[0, 90, 180, 270]` avant alignement fin.
2. Garder la meilleure combinaison `(rotation, méthode, score)`.
3. Persister sur `Submission` :
   - `alignment_score`,
   - `alignment_method`,
   - `alignment_rotation`.

### Étape PR3.4 — Observabilité
1. Ajouter logs structurés : nb keypoints, nb inliers, méthode retenue.
2. (Optionnel) stocker une image d’overlay de debug en artifact.

---

## PR4 — Pipeline V2

### Étape PR4.1 — Nouveau flux principal
Refactor `process_submission_pipeline` en séquence :
1. Charger template actif de `ExamVersion`.
2. Split PDF en pages.
3. Pour chaque page :
   - aligner la page avec la page template correspondante,
   - projeter/cropper les `TemplateZone`,
   - OCR par zone,
   - créer `AnswerBlock` avec `question_key`.

### Étape PR4.2 — OCR par zone
1. Ajouter dans `ocr_service` une méthode dédiée :
   - `extract_text_from_crop(image_bytes, bbox, preprocessing=...)`.
2. Prétraitements image légers (grayscale, threshold adaptatif) avant OCR.
3. Détecter “zone vide / encre absente” (ratio encre) avant appel OCR coûteux.

### Étape PR4.3 — Règles de statut submission
Définir une matrice de décision explicite, par exemple :
- `PROCESSED` si alignement >= seuil et au moins X% zones traitées correctement.
- `NEEDS_REVIEW` si score alignement moyen/faible ou trop de zones vides ambiguës.
- `ERROR` si alignement impossible sur toutes les pages.

### Étape PR4.4 — Compatibilité descendante
1. Garder le pipeline actuel derrière un feature flag (ex: `PIPELINE_V2_ENABLED`).
2. Permettre rollback rapide en prod.

---

## PR5 — Stratégie de tests

### Étape PR5.1 — Tests extraction template
1. Unit tests sur `extract_template_zones_from_pdf` :
   - pattern de question reconnu/non reconnu,
   - robustesse pages multiples,
   - bbox valides.
2. API tests déjà existants à compléter :
   - validation globale,
   - patch bulk,
   - idempotence re-extraction.

### Étape PR5.2 — Tests alignement
1. Jeux de fixtures image :
   - même page,
   - rotation 90/180,
   - bruit léger,
   - cas d’échec.
2. Vérifier méthode choisie, score, rotation et bornes attendues.

### Étape PR5.3 — Tests OCR par zone
1. Mock OCR provider pour stabilité CI.
2. Vérifier :
   - crop correct selon bbox,
   - détection zone vide,
   - mapping transcription → `AnswerBlock`.

### Étape PR5.4 — Tests pipeline complet
1. Test d’intégration `template -> alignement -> zones -> OCR`.
2. Assertions :
   - nombre d’`AnswerBlock` = nombre de zones traitées,
   - `submission.status` conforme aux règles,
   - champs d’alignement persistés.

---

## 3) Ordre de livraison recommandé (sprints)

### Sprint A (PR2 durci)
- Finaliser endpoints template (validation globale + bulk patch).
- Durcir extraction PyMuPDF + tests extraction.

### Sprint B (PR3)
- Livrer service alignement complet ORB/AKAZE/ECC + rotation + score.
- Ajouter tests unitaires alignement.

### Sprint C (PR4)
- Intégrer alignement et OCR par zone dans pipeline V2 (feature flag).
- Ajouter règles status et tests d’intégration ciblés.

### Sprint D (PR5 finalisation)
- Compléter matrice de tests e2e, stabiliser fixtures et mocks.
- Ajouter métriques de non-régression (temps, taux de succès alignement).

---

## 4) Critères d’acceptation (DoD)

- **PR2** : un prof peut uploader un template, voir les zones, ajuster, valider ; les coordonnées finales sont persistées et historisées.
- **PR3** : chaque soumission reçoit `alignment_score`, `alignment_method`, `alignment_rotation` avec fallback robuste.
- **PR4** : pipeline V2 produit des `AnswerBlock` par zones template avec OCR, et statut cohérent.
- **PR5** : suite de tests automatisés couvre extraction, alignement, OCR zone et pipeline complet.
