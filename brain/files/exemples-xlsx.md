# exemple_clients_DIVE*.xlsx
> Jeux de données fictifs pour tester l'outil. Aucune donnée réelle.

| Fichier | Rôle |
|---|---|
| `exemple_clients_DIVE.xlsx` | Original. Feuille **Clients** (250 lignes × 13 col. : N° client, Société, Contact, E-mail, Téléphone, Ville, Pays, IBAN, Date de naissance du contact, Type de turbine, Puissance installée (kW), CA 2025 (€), Commentaire) et feuille **Projets** (180 × 10 : N° projet, N° client, Contact client, Site, Type de turbine, Hauteur de chute (m), Montant du devis (€), Date de mise en service, Statut, Chef de projet). |
| `exemple_clients_DIVE_chiffre.xlsx` | Sortie de `encrypt`/« Protéger » : colonnes A–I de Clients masquées avec en-têtes masqués (`HEADER_0001`…) et jetons lisibles. |
| `exemple_clients_DIVE_chiffre_dechiffre.xlsx` | Sortie de `decrypt`/« Restaurer » du fichier précédent : doit être identique à l'original (test aller-retour). |

Convention de nommage des sorties : `<nom>_chiffre.<ext>` puis `<nom>_dechiffre.<ext>`.
Couvre les détecteurs : e-mails, téléphones FR/DE, IBAN, dates, noms propagés dans *Commentaire* et *Contact client*.
