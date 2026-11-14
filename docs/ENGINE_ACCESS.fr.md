<sub>🇬🇧 <a href="ENGINE_ACCESS.md">English</a> · 🇫🇷 <b>Français</b> · <a href="../README.fr.md">← README</a></sub>

# Configurer l'accès au moteur — y compris privé

Le moteur n'est pas livré ici. Il est localisé à l'exécution. C'est tout
l'objet : ce gateway peut être public pendant que le moteur qu'il invoque est
privé.

---

## Les trois variables

| Variable | Ce qu'elle fait | Obligatoire |
|---|---|---|
| `EVIDENCE_ENGINE_HOME` | répertoire du moteur Evidence (`verify.py` à sa racine) | **oui** |
| `EVIDENCE_PYTHON` | interpréteur employé pour lancer le moteur ; par défaut celui qui exécute le gateway | non |
| `EVIDENCE_ENGINE_REVISION` | révision que l'opérateur **déclare** pour le moteur. Republiée avec cette réserve, jamais vérifiée | non |

`--engine-home` en ligne de commande l'emporte sur `EVIDENCE_ENGINE_HOME`.

Il n'y a **aucun chemin par défaut**. En deviner un ferait passer une absence
de configuration pour un moteur en panne. Si rien n'est déclaré, le gateway
répond `engine_not_declared` et le code de sortie `3`.

```sh
export EVIDENCE_ENGINE_HOME=/srv/evidence            # un clone privé convient
export EVIDENCE_ENGINE_REVISION=3391c768             # déclarée, non vérifiée
python gateway.py engine                             # ce qui est atteignable, et ce qui est déclaré
```

## Ce que le gateway attend du moteur

Exactement ceci, et rien de plus :

| Besoin | Pourquoi |
|---|---|
| `verify.py` à la racine du moteur | l'opération `verify` |
| `verify_attestation.py` à la racine du moteur | l'opération `attestation` |
| les deux acceptent `--json <fichier>`, `--lang`, `--strict` | le gateway lit le **rapport machine**, jamais la sortie texte |
| un Python opérationnel pour le moteur | exigence du moteur, pas du gateway |

Un accès en lecture seule suffit. Le gateway fait écrire le rapport du moteur
dans son propre répertoire temporaire, jamais dans l'arbre du moteur.

Facultatifs, et lus seulement s'ils sont présents :

- `conformance/VERSION` → republié en `engine.conformance_corpus_declared` ;
- `schemas/*.json` → listés par `gateway.py contracts`.

## Ce dont il n'a pas besoin, et qu'il ne faut jamais lui donner

- **aucune copie du moteur.** L'embarquer ici ferait de ce dépôt une
  redistribution du moteur, et une seconde chose à maintenir en phase.
- **aucun accès réseau au moteur.** Le moteur n'a aucune interface HTTP ; le
  gateway l'invoque comme un processus local. Une intégration qui a besoin
  d'une frontière réseau place *ce gateway* derrière elle — le gateway reste
  à côté du moteur.
- **aucune clé de signature, aucun matériel de signature de magasin de
  confiance, aucun secret de pilote.** Le gateway ne vérifie rien et ne signe
  rien ; il n'en a aucun usage.

## Quand le moteur devient privé

Rien ne change dans ce gateway. Ce qui change est du côté du moteur, et vaut
d'être dit en clair :

| Ce qui casse | Conséquence |
|---|---|
| `https://raw.githubusercontent.com/.../neomundi-evidence-public/main/trust/trust-store.json` | le magasin de confiance public ne répond plus. Un intégrateur qui le récupérait à cette URL doit recevoir un autre canal **avant** la privatisation, pas après |
| les liens publics du moteur, ses badges de CI, son corpus de conformité | inatteignables pour qui n'a pas d'accès |
| le `git clone` du moteur par un intégrateur | exige une autorisation |

La configuration propre au gateway n'est pas touchée : un clone privé en
`EVIDENCE_ENGINE_HOME` fonctionne exactement comme un clone public.

## Le moteur le plus simple : celui publié à côté

Depuis le 14 novembre 2026, ce dépôt publie aussi la part **vérification** du
moteur, dans [`../verifier/`](../verifier). Elle satisfait chaque exigence du
tableau ci-dessus : elle peut donc servir de moteur directement.

```sh
export EVIDENCE_ENGINE_HOME="$PWD/verifier"
python gateway.py engine          # disponible : true, corpus de conformite 1.3.0
```

Mesuré le 2026-11-14, gateway pointé là plutôt que sur le moteur privé : les
cinq scénarios rendent **0 / 1 / 2 / 4 / 3**, avec des fixtures du corpus
comme artefacts. Ce qui reste privé est ce qui *produit et signe* — aucune
configuration ne ramène cette part.

## La moitié du contrat s'éprouve sans aucun moteur

Les deux états qui disent *aucune vérification n'a eu lieu* — `rejected` et
`engine_unavailable` — n'exigent aucun moteur :

```sh
python tests/test_gateway.py      # les cas 4 et 5 tournent sans moteur
sh demo/demo.sh --no-engine
```

C'est délibéré. Un intégrateur à qui le moteur n'a pas été ouvert peut tout
de même qualifier l'enveloppe, les raisons de refus et les codes de sortie.
