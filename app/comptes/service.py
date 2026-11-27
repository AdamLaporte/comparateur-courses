"""Comptes et favoris (lot 2). BOUCHON : rien n'est encore implémenté.

À faire :
- inscription / connexion par e-mail et mot de passe, haché avec pwdlib (argon2) :
  `from pwdlib import PasswordHash ; hacheur = PasswordHash.recommended()` ;
- à la connexion, poser `request.session["utilisateur_id"]` (app/panier/service.py s'en sert pour lier
  la liste à l'utilisateur) ; à la déconnexion, l'enlever ;
- articles favoris (table article_favori) et adresses favorites (table adresse_favorite), voir schema.sql.
Tables créées au démarrage à partir de schema.sql.
"""
