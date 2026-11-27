# 2026-11-27 : jade : comptes, connexion

- **Agent / personne** : Claude Code piloté par Jade
- **Branche** : `claude/nifty-curie-x3h69j` (branche imposée par la session cloud)
- **Lot** : 2, partie comptes (reprise par Jade avec l'accord de son responsable)

## Fait

- Inscription, connexion, déconnexion, changement de mot de passe, mot de passe perdu avec lien de réinitialisation.
- La liste faite sans compte est gardée dans le compte à la connexion.
- Pages : `app/templates/comptes/` (page, inscription, connexion, mot_de_passe, mot_de_passe_perdu, reinitialiser),
  styles de formulaire dans `style.css`, lien du menu « Se connecter » / « Mon compte ».
- Articles favoris : « ☆ Favori » sur chaque ligne de la liste (connecté), page `/comptes/favoris` (ajouter à la liste,
  tout ajouter, retirer), sans doublon.
- Suggestions d'articles : plus de « None » quand Open Food Facts ne donne pas de marque ou de quantité.
- « Maison » : code postal enregistré, bouton « 🏠 Maison » sur l'accueil, « Enregistrer comme maison » sur la page des
  magasins, code postal par défaut à la connexion.
- 22 tests dans `tests/test_comptes.py` ; 69 tests verts, ruff propre. Parcours vérifiés dans un navigateur.

## Fichiers modifiés

- `app/comptes/service.py`, `app/comptes/routes.py`
- `app/templates/comptes/*.html` (dont `favoris.html`), `app/static/style.css` (ajouts en fin de fichier)
- Lot 1, ajouts : `panier/_liste.html` (bouton favori), `panier/page.html` (lien « mes favoris »),
  `produits/_suggestions.html` (marque ou quantité absente), `magasins/accueil.html` et `magasins/liste.html` (maison)
- Partagés (commit à part) : `app/config.py`, `.env.example` (SMTP), `app/templates/base.html` (menu)
- `tests/test_comptes.py`, `docs/decisions.md`, `docs/taches.md`, `docs/architecture.md`

## Décisions prises

- Voir les lignes « Comptes » et « SMTP » du 27/11 dans `docs/decisions.md`.

## Reste à faire

- Cagnotte : écart avec la moyenne des magasins comparés, au clic « J'ai fait mes courses ici » (décision du 27/11).

## Points d'attention pour la suite

- Sans SMTP, le lien « mot de passe perdu » est dans le terminal du serveur (ligne « lien de réinitialisation »).
- Le blocage après 5 échecs est en mémoire : il repart de zéro au redémarrage du serveur.
- Changer `SECRET_KEY` déconnecte tout le monde et invalide les liens en cours.
