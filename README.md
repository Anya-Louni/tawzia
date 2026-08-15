# Tawzia

**La plateforme RH et de planification conçue pour l'Algérie.**

Recruter, planifier, payer, se conformer, décider. Sur le vrai calendrier
algérien, la vraie météo et le vrai droit du travail.

> Le récit commercial et le dimensionnement du marché sont dans
> [`PITCH.md`](PITCH.md). La provenance de chaque chiffre est dans
> [`SOURCES.md`](SOURCES.md). Pour dérouler une démonstration, suivez
> [`DEMO_GUIDE.md`](DEMO_GUIDE.md).

---

## Pourquoi cet outil existe

Les logiciels RH internationaux sont bâtis pour un monde grégorien, avec un
week-end samedi-dimanche et un climat tempéré. En Algérie ils se trompent par
construction : le week-end est **vendredi-samedi**, les deux plus gros
événements de l'année (le Ramadan et les deux Aïd) reculent d'environ 11 jours
chaque année sur le **calendrier hégirien**, et l'été n'est pas un creux mais le
**pic du retour de la diaspora**.

Ces trois faits sont des entrées de première classe ici, pas des options. Et
l'application mesure ce qu'ils valent, en comparant le même algorithme avec et
sans eux.

## Ce que contient l'application

29 écrans, répartis en sept sections. Le bandeau supérieur les montre toutes ;
cliquer sur une section assombrit l'écran et présente ses fonctionnalités.

### Accueil
| Écran | Ce qu'il fait |
|---|---|
| **Accueil** | Le point d'entrée : ce que fait la plateforme, par où commencer, l'engagement d'honnêteté. Une visite guidée se lance au premier lancement. |
| **Tableau de bord** | L'écran du matin : charge prévue par shift, planning recommandé et son coût chargé, événements du calendrier à venir. |

### Recrutement
| Écran | Ce qu'il fait |
|---|---|
| **Sourcing & marque employeur** | Par quels canaux algériens réels faire venir des candidats : universités, écoles nationales, réseau CFPA/INSFP, ANEM, sites d'emploi. Classés par adéquation métier, proximité, coût et délai, avec un plan chiffré et un message de prise de contact. |
| **Évaluation de CV** | Déposez un CV, obtenez un verdict adapté au contexte algérien (formation LMD, service national, langues, permis, mobilité), les lacunes et des questions d'entretien. Détecte les CV qui tentent de manipuler le tri automatique. |
| **Rédiger une offre** | Une phrase suffit : l'annonce est écrite, le salaire et les conditions sont calculés sur votre équipe et le droit algérien. |
| **Vivier de candidats** | Toutes les candidatures classées du mieux au moins adapté, avec filtres et profil détaillé. Le classement est explicable critère par critère. |
| **Appariement CV/poste** | Classe un lot de candidats face à une offre par embeddings locaux. Sans clé d'API, hors ligne, reproductible. |

### Équipe & présence
| Écran | Ce qu'il fait |
|---|---|
| **Employés** | Le registre du personnel et les droits à congé calculés sur les entitlements légaux réels. |
| **Demandes & présence** | Congés, sorties, retards et absences, arbitrés avec la charge prévue de la semaine. |
| **Compétences & mobilité** | Qui, dans l'effectif, peut déjà tenir le poste à pourvoir, ce qu'il lui manque, et l'arbitrage chiffré former ou recruter. |
| **Risque de départ** | Qui risque de partir dans six mois, pourquoi, et ce que coûte son remplacement. |
| **Négociateur de rétention** | L'action la moins chère pour garder un salarié, avec le script d'entretien. |

### Planification
| Écran | Ce qu'il fait |
|---|---|
| **Prévision de la demande** | La charge attendue par shift, avec des intervalles p10-p90 dérivés de l'erreur réelle du backtest. Chaque journée porte la raison de son allure. |
| **Planning & coût** | Le roster le moins cher qui respecte la loi : plafond d'heures supplémentaires, repos hebdomadaire, niveau de service. |
| **Analyse sectorielle** | La fonctionnalité propre au secteur choisi, qui change avec le type d'activité. |
| **Aéroport** | Module aviation, visible seulement en édition aéroport : flux passagers vers effectif de terminal, prédiction de cascade de retards, risque de rotation. Sur le réseau réel d'Alger. |

### Paie & conformité
| Écran | Ce qu'il fait |
|---|---|
| **Paie** | Bulletins, CNAS et IRG calculés sur le barème algérien. |
| **Échéances & déclarations** | Ce que le comptable doit déposer à la CNAS et aux impôts, avant quand, avec le lien du portail officiel et un export agenda. |
| **Détection d'anomalies** | Les écarts de paie et de présence qu'un contrôle relèverait avant vous. |
| **Contrôle de documents** | Un modèle de vision entraîné lit les montants d'un bulletin, et la plateforme les confronte au SNMG, au taux CNAS et au volume horaire légal. |
| **Simulateur d'inspection** | Ce que verrait un inspecteur du travail s'il passait aujourd'hui. |
| **Veille Journal Officiel** | Les textes parus qui changent vos obligations. |

### Décision IA
| Écran | Ce qu'il fait |
|---|---|
| **Tableau de KPI** | Les indicateurs qui décident, suivis dans le temps. |
| **Simulateur de scénarios** | Volume, effectif, salaires : l'effet chiffré avant de trancher. |
| **Assistant** | Une seule conversation pour toute la plateforme : planning, personnel, paie, décisions. Un routeur choisit le domaine et ne donne au modèle que les chiffres concernés. Bâti sur assistant-ui. |
| **Données de l'entreprise** | Importez votre fichier : toute la plateforme bascule sur vos vrais chiffres. |

### Preuves & sources
| Écran | Ce qu'il fait |
|---|---|
| **Preuves** | Le backtest walk-forward contre un modèle international générique et des baselines naïves, la comparaison en argent hors échantillon, l'importance des variables. La page de crédibilité. |
| **Calendrier algérien** | Pourquoi un outil étranger se trompe ici, avec une vérification en direct contre le calendrier de référence. |
| **Analyse économique** | Dimensionnement du marché et économie unitaire, avec un prix dérivé de l'économie mesurée. |
| **Confidentialité** | Ce qui est traité, ce qui sort vers un service tiers, et combien de temps c'est conservé. |
| **Sources & hypothèses** | Chaque chiffre externe et chaque hypothèse, cités. |

> **Les volumes opérationnels de la démonstration sont simulés.** Aucun registre
> d'entreprise algérienne n'est public. Le calendrier, la météo et le droit
> auxquels ils répondent sont réels, et l'application le dit sur chaque page.

---

## Installation

### 1. Prérequis
- **Python 3.10 ou plus récent**, à vérifier avec `python --version`

### 2. Environnement et dépendances

Windows (PowerShell) :

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS ou Linux :

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

Si PowerShell bloque l'activation :
`Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`, puis
recommencez.

`requirements.txt` installe aussi le composant de conversation depuis
`components/tawzia-chat`. Ses fichiers JavaScript sont déjà construits et
versionnés, donc aucune installation Node n'est nécessaire pour faire tourner
l'application.

### 3. Lancer

```bash
streamlit run dashboard.py
```

L'application s'ouvre sur `http://localhost:8501`.

Le premier affichage récupère la météo réelle et lance un backtest walk-forward,
ce qui prend environ **trois minutes**. Le résultat est ensuite persisté sur
disque et les affichages suivants prennent quelques secondes, y compris après un
redémarrage.

**Avant une démonstration**, ouvrez le tableau de bord une fois pour chaque
activité et chaque wilaya que vous comptez montrer. Une combinaison jamais
ouverte repaie ces trois minutes devant le client.

### 4. Clé IA, facultative

Les copilotes et l'assistant utilisent [Groq](https://console.groq.com), dont
l'offre gratuite ne demande pas de carte. Créez un fichier `.env` à la racine :

```
GROQ_API_KEY=gsk_votre_cle_ici
```

`.env` est ignoré par git. Tous les modèles maison (prévision, optimiseur,
attrition, appariement de CV, lecture de documents) tournent sans clé.

### Démonstration hors ligne

Ouvrez l'application une fois avec une connexion pour remplir les caches, puis
désactivez **Données → Autoriser les appels API en direct** dans le bandeau.
Tout tourne ensuite depuis `data/cache/`.

---

## Structure du projet

```
.
├── dashboard.py                  # Point d'entrée, navigation sur les 29 pages
├── app_pages/                    # Un fichier par écran
├── core/                         # Le moteur, chaque module s'auto-teste
│   ├── sources.py                # Registre unique des chiffres cités et des hypothèses
│   ├── calendar_dz.py            # Conversion hégirienne, fêtes, moteurs saisonniers
│   ├── weather_dz.py             # Open-Meteo par wilaya, avec repli hors ligne
│   ├── labour_dz.py              # SNMG, CNAS, rôles, shifts
│   ├── payroll_dz.py             # Bulletins, IRG, déclarations
│   ├── demand.py                 # Volumes simulés sur calendrier et météo réels
│   ├── forecast.py               # Backtest walk-forward, prévision boostée
│   ├── staffing.py               # Optimiseur de roster et baseline de comparaison
│   ├── attrition.py              # Risque de départ interprétable
│   ├── skills.py                 # Compétences, mobilité interne, former ou recruter
│   ├── sourcing.py               # Canaux de sourcing réels et plan chiffré
│   ├── vision.py                 # Lecteur de chiffres entraîné, contrôle de documents
│   ├── cv_screen.py              # Lecture de CV et défense contre l'injection
│   ├── matching.py               # Appariement CV/poste par embeddings locaux
│   ├── aviation.py               # Réseau de vols d'Alger
│   ├── delay_cascade.py          # Propagation de retard et vol pivot
│   ├── nav.py                    # Bandeau et sélecteur de fonctionnalités
│   ├── tour.py                   # Visite guidée (driver.js embarqué)
│   └── appdata.py                # Chargeurs mis en cache, thème, état partagé
├── components/tawzia-chat/    # Composant de conversation (assistant-ui, CCv2)
├── assets/vendor/                # driver.js embarqué, aucun CDN à l'exécution
├── DESIGN.md                     # Le système visuel et ses règles
├── DEMO_GUIDE.md                 # Comment dérouler une démonstration
├── PITCH.md                      # Récit commercial
├── SOURCES.md                    # Provenance de chaque chiffre
└── data/cache/                   # Réponses d'API mises en cache (ignoré par git)
```

### Vérifier le moteur

Chaque module du moteur porte son propre auto-contrôle :

```bash
python -m core.calendar_dz     # aller-retour hégirien et week-end
python -m core.labour_dz       # pile de coûts, retrouve le plancher de 138,46 DZD/h
python -m core.forecast        # backtest walk-forward contre les baselines
python -m core.vision          # entraîne le lecteur de chiffres et affiche son exactitude
python -m core.sourcing        # classement des canaux de recrutement
python -m core.skills          # écart de compétences et mobilité interne
python -m core.pipeline        # économie de bout en bout, hors échantillon
```

---

## Dépannage

**Le premier affichage est long.** Il récupère la météo réelle et lance un
backtest sur une trentaine d'origines. Environ trois minutes, puis c'est persisté
sur disque.

**`ModuleNotFoundError`.** L'environnement virtuel n'est pas actif, ou les
dépendances ne sont pas installées. Voir l'étape 2.

**Un copilote signale l'absence de `GROQ_API_KEY`.** Attendu sans clé. Toutes les
autres pages fonctionnent. Voir l'étape 4.

**Le port 8501 est occupé.**
`streamlit run dashboard.py --server.port 8502`

**Une valeur météo ou macro affiche « repli hors ligne ».** L'API n'était pas
joignable et rien n'était encore en cache. Connectez-vous une fois et rechargez.
