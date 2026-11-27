# 2026-11-27 : jade : comptes, connexion

- **Agent / personne** : Claude Code piloté par Jade
- **Branche** : `claude/nifty-curie-x3h69j` (branche imposée par la session cloud)
- **Lot** : 2, partie comptes (reprise par Jade avec l'accord de son responsable)

## Fait

- Inscription, connexion, déconnexion, changement de mot de passe, mot de passe perdu avec lien de réinitialisation.
- La liste faite sans compte est gardée dans le compte à la connexion.
- Pages : `app/templates/comptes/` (page, inscription, connexion, mot_de_passe, mot_de_passe_perdu, reinitialiser),
  styles de formulaire dans `style.css`, lien du menu « Se connecter » / « Mon compte ».
- 15 tests dans `tests/test_comptes.py` ; 62 tests verts, ruff propre. Parcours vérifié dans un navigateur.

## Fichiers modifiés

- `app/comptes/service.py`, `app/comptes/routes.py`
- `app/templates/comptes/*.html`, `app/static/style.css` (ajout en fin de fichier)
- Partagés (commit à part) : `app/config.py`, `.env.example` (SMTP), `app/templates/base.html` (menu)
- `tests/test_comptes.py`, `docs/decisions.md`, `docs/taches.md`, `docs/architecture.md`

## Décisions prises

- Voir les lignes « Comptes » et « SMTP » du 27/11 dans `docs/decisions.md`.

## Reste à faire

- Articles favoris (table `article_favori` déjà créée), « maison » (table `adresse_favorite`), cagnotte (à concevoir).

## Points d'attention pour la suite

- Sans SMTP, le lien « mot de passe perdu » est dans le terminal du serveur (ligne « lien de réinitialisation »).
- Le blocage après 5 échecs est en mémoire : il repart de zéro au redémarrage du serveur.
- Changer `SECRET_KEY` déconnecte tout le monde et invalide les liens en cours.
