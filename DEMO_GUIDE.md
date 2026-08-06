# Guide de démonstration , WorkForce.dz

La plateforme RH et de planification par l'IA, conçue pour le droit du travail
algérien et adaptable à **tout secteur**. Ce guide sert à (1) connaître toutes
les fonctionnalités et (2) dérouler une démonstration convaincante devant un
client potentiel.

---

## 1. Toutes les fonctionnalités

Sept sections dans le menu de gauche, organisées par métier.

### Accueil
- **Accueil** , page d'entrée : ce que fait la plateforme, par où commencer, et
  l'engagement d'honnêteté (réel vs simulé).
- **Tableau de bord** , l'écran du matin : demande prévue par shift, planning
  recommandé et son coût chargé, événements du calendrier algérien à venir, et un
  **Spotlight secteur** qui change selon l'activité choisie.

### Recrutement
- **Évaluation de CV** , déposez un CV (PDF/texte), l'IA rend un verdict adapté au
  contexte algérien (formation LMD, service national, langues, permis, mobilité),
  points forts/faibles et questions d'entretien sur mesure.
- **Appariement CV/poste** , classez un lot de CV contre un poste par
  **embeddings locaux** (sans clé, hors ligne, reproductible), combinés à la
  grille structurée algérienne.

### Équipe & présence
- **Employés** , l'annuaire du personnel et ses droits (congés acquis, ancienneté,
  brut mensuel), sur les entitlements légaux réels.
- **Demandes & présence** , congés, demandes de sortie, retards et absences, avec
  une recommandation légale + opérationnelle pour chaque demande.
- **Risque de départ** , qui risque de partir, pourquoi, et le coût de son
  remplacement (modèle d'attrition interprétable).
- **Négociateur de rétention** , l'action la moins chère pour retenir un employé,
  avec le script d'entretien.

### Planification
- **Prévision de la demande** , la charge attendue par shift, avec intervalles
  p10-p90 dérivés de l'erreur réelle du backtest (pas d'intervalle supposé).
- **Planning & coût** , le roster le moins cher qui respecte la loi (plafond
  d'heures sup., repos hebdomadaire, niveau de service).
- **Analyse sectorielle** , la fonctionnalité **propre au secteur choisi** (voir
  la liste des secteurs plus bas). Change instantanément avec le « Type
  d'activité ».
- **Aéroport** , flux passagers et cascade de retards (visible uniquement en
  édition aéroport).

### Paie & conformité
- **Paie** , bulletins et déclarations CNAS/IRG calculés sur la vraie pile
  SNMG + CNAS + IRG.
- **Détection d'anomalies** , erreurs de paie et signaux de présence, repérés
  avant l'audit ou la démission : règles algériennes interprétables + un modèle
  non supervisé (IsolationForest) ajusté sur les données de l'entreprise.
- **Simulateur d'inspection** , passez l'inspection du travail sur vous-même :
  articles, amendes indicatives, corrections.
- **Veille Journal Officiel** , vérifie que vos paramètres sont à jour et simule
  l'impact d'un changement de règle.

### Décision IA
- **Tableau de KPI** , les indicateurs clés effectif / coût / présence / risque,
  avec bandes de santé (bon / à surveiller / critique).
- **Simulateur de scénarios** , le « et si ? » chiffré : hausse de salaire, SNMG,
  embauche, absentéisme, heures sup. vs intérim, référence vs scénario avec
  l'écart sur chaque ligne.
- **Copilote décisionnel** , posez une question de gestion : il répond à partir
  des **vrais chiffres de l'entreprise** (KPI, anomalies, risque), recommande une
  action, et propose le scénario à simuler. Il n'invente aucun chiffre.
- **Copilote RH** / **Assistant opérations** , questions en langage naturel, l'IA
  répond sur vos données.
- **Données de l'entreprise** , importez votre fichier du personnel et de présence
  (CSV, colonnes reconnues en FR/EN) : toutes les pages ci-dessus basculent alors
  sur vos vraies données.

### Preuves & sources
- **Preuves** , le backtest qui prouve la méthode (hors échantillon).
- **Calendrier algérien** , Ramadan, les deux Aïds, Yennayer, jours fériés,
  week-end vendredi-samedi , calculés et vérifiés.
- **Analyse économique** , le business case et les hypothèses de coût.
- **Sources & hypothèses** , chaque chiffre : mesuré (cité), live (API), ou
  hypothèse (assumée).

### Personnalisation par secteur (« Type d'activité »)
Change les rôles, la demande, et surtout l'**Analyse sectorielle** :
| Secteur | Fonctionnalité propre |
|---|---|
| Hub e-commerce | Trésorerie COD & retours (espèces transportées, retours, valeur immobilisée) |
| Assistance aéroportuaire | Vague diaspora & pointe passagers |
| Distribution retail | Vague Ramadan / pré-Aïd (renfort de picking à pré-réserver) |
| Hôtellerie | Charge ménage selon l'occupation |
| Transport & flotte | Conformité temps de conduite |
| **Établissement scolaire** | Calendrier scolaire & encadrement (rentrée, trimestres, examens BEM/BAC) |

---

## 2. Le parcours de démonstration (≈ 12-15 min)

Objectif : faire dire au client « ça, c'est fait pour nous ». Suivez le fil ,
chaque étape a un point à marteler.

### Étape 0 , Cadrer (30 s)
> « WorkForce.dz prévoit votre charge, planifie chaque shift **légalement**, gère
> la paie et la conformité algériennes, et vous aide à **décider** , le tout sur
> le vrai calendrier et le droit du travail algériens. »

Ouvrez l'**Accueil**. Montrez les badges : droit du travail algérien, IA locale,
tous secteurs.

### Étape 1 , Le parler leur langue (1 min)
Dans la barre latérale, changez le **Type d'activité** vers le secteur du client
(ex. *Établissement scolaire*). Ouvrez **Planification › Analyse sectorielle**.
> « L'outil s'adapte : pour une école, on ne parle pas de colis mais de rentrée,
> de trimestres et d'examens BEM/BAC , avec le calendrier scolaire algérien et le
> renfort de surveillance à prévoir. »

**Le point :** ce n'est pas un tableur générique, c'est *leur* métier.

### Étape 2 , L'écran du matin (2 min)
Ouvrez **Tableau de bord**. Montrez la demande prévue, le planning recommandé,
son coût, et le **Spotlight secteur**.
> « Voici ce qu'un responsable ouvre chaque matin : combien de monde il faut,
> quand, et ce que ça coûte , charges patronales CNAS incluses, ce que la plupart
> des plannings oublient. »

**Le point :** l'intervalle p10-p90 vient de l'erreur réelle mesurée, pas d'une
hypothèse.

### Étape 3 , Recrutement intelligent (2 min)
Ouvrez **Recrutement › Appariement CV/poste**. Chargez le poste exemple, cochez
les CV exemples, cliquez **Classer les candidats**.
> « On classe les candidats par proximité au poste avec des **embeddings
> calculés sur votre machine** , aucune donnée candidat ne sort. Et la grille
> reste algérienne : service national, permis, langues. »

**Le point :** intelligent *et* privé *et* défendable (score reproductible).

### Étape 4 , Paie & anomalies (2 min)
Ouvrez **Paie & conformité › Détection d'anomalies**.
> « Les erreurs qui coûtent cher , un salaire sous le SNMG, une bande IRG à
> vérifier, un absentéisme qui explose , repérées **avant** l'inspection CNAS/DGI
> ou la démission. Les règles sont citées ; le modèle apprend le *normal* de
> votre entreprise. »

**Le point :** on ne fait pas que calculer la paie, on la **contrôle**.

### Étape 5 , Piloter et décider (3 min)
Ouvrez **Décision IA › Tableau de KPI** (montrez les bandes de santé), puis
**Simulateur de scénarios**.
> « Testez une décision avant de la prendre : et si on augmente de 8 % ? si le
> SNMG remonte ? si on ramène l'absentéisme à 4 % ? Chaque levier est recalculé
> sur la vraie pile de coûts, référence contre scénario. »

Puis **Copilote décisionnel** : cliquez une question suggérée (« Sommes-nous en
règle côté paie et CNAS/IRG ? »).
> « Le copilote ne brode pas : il répond à partir des chiffres réels calculés par
> nos modèles, et cite les indicateurs. L'IA rédige la décision ; les modèles
> maison produisent les chiffres. »

**Le point :** c'est un copilote *fondé sur leurs données*, pas un chatbot.

### Étape 6 , Le moment « vos données » (2 min)
Ouvrez **Décision IA › Données de l'entreprise**. Montrez le modèle de fichier,
importez un CSV (ou le modèle rempli).
> « Jusqu'ici c'était une démonstration clairement étiquetée. Vous importez votre
> fichier , et **toutes** ces pages basculent sur vos vrais chiffres, en restant
> dans votre session. La méthode ne change pas. »

**Le point :** pas d'enfermement, pas de longue intégration , la valeur est
immédiate.

### Étape 7 , Clore sur l'honnêteté (1 min)
Ouvrez **Preuves & sources › Sources & hypothèses**.
> « On distingue toujours ce qui est **mesuré et cité**, ce qui est **live** (API
> publiques), et ce qui est une **hypothèse** que vous remplacez par vos chiffres.
> Le calendrier, la météo, le droit du travail et la fiscalité sont réels. »

**Le point :** on ne survend rien , c'est ce qui rend le reste crédible.

---

## 3. Réponses aux objections courantes

- **« Vos volumes sont-ils réels ? »** , Pour la démo, non, et c'est écrit sur
  chaque page : aucun registre d'entreprise algérienne n'est public. Le calendrier,
  la météo, le droit du travail et la fiscalité, eux, sont réels. Sur vos données,
  les mêmes modèles tournent à l'identique.
- **« Faut-il une clé/abonnement IA ? »** , Non pour l'essentiel : prévision,
  optimiseur, attrition, appariement CV, anomalies tournent **localement sans
  clé**. Une clé (gratuite) n'ajoute que la couche langage naturel.
- **« Nos données quittent-elles nos locaux ? »** , L'import reste dans la
  session ; l'appariement CV et les modèles maison tournent sur l'appareil. Seule
  la couche langage envoie le texte au fournisseur si vous l'activez.
- **« On n'a pas Internet stable sur site. »** , Mode hors-ligne : météo et macro
  sont mises en cache au premier appel, tout continue de fonctionner.
- **« On n'est pas dans la logistique. »** , Choisissez votre secteur dans « Type
  d'activité » , hôtellerie, transport, retail, école… , l'app se réadapte.

---

## 4. Aide-mémoire , le chemin le plus court

Accueil → (choisir le secteur) Analyse sectorielle → Tableau de bord →
Appariement CV/poste → Détection d'anomalies → Tableau de KPI → Simulateur de
scénarios → Copilote décisionnel → Données de l'entreprise → Sources.

> Une phrase pour finir : *« Un seul outil qui prévoit, planifie légalement, paie,
> contrôle et décide , sur l'Algérie réelle, et sur vos données dès aujourd'hui. »*
