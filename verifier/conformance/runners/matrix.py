#!/usr/bin/env python3
"""Matrice de couverture — croise les règles, les familles et les résultats.

    python conformance/runners/matrix.py --results rapport.json --out matrice.md

CE QUE CETTE MATRICE PERMET DE VOIR, ET C'EST SON SEUL OBJET
============================================================

  1. les règles **couvertes** par au moins un cas ;
  2. les règles **non couvertes** — par construction, ce que le corpus ne
     cite pas n'apparaît pas, et c'est la limite qu'il faut lire en premier ;
  3. les règles **ambiguës**, que le corpus consigne sans trancher ;
  4. les cas **non applicables** à un vérificateur donné ;
  5. les comportements **propres à une implémentation** ;
  6. les **régressions**, par comparaison à `known_failures.json`.

LE DÉNOMINATEUR EST TOUJOURS ÉCRIT
==================================

Un taux sans son dénominateur ne veut rien dire. Chaque pourcentage de ce
document porte donc le nombre de cas **applicables au vérificateur
concerné** — jamais le total du corpus, qui compterait contre `rust-core`
des cas d'archive qu'il n'annonce pas traiter.

ET CE QUE LA MATRICE N'ÉTABLIT PAS
==================================

Elle mesure la conformité aux règles **que le corpus cite**. Elle ne dit
rien des règles qu'il ne cite pas, et un corpus de 50 cas ne couvre pas un
protocole. « 100 % » y serait donc un chiffre faux, et le document refuse de
l'écrire.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

CORPUS = Path(__file__).resolve().parent.parent


def charger_fiches() -> list[dict]:
    return [json.loads(p.read_bytes())
            for p in sorted((CORPUS / "expected").glob("*.json"))]


def rendre(fiches: list[dict], resultats: dict | None) -> str:
    version = (CORPUS / "VERSION").read_text().strip()
    par_id = {f["id"]: f for f in fiches}
    verificateurs = resultats["verifiers"] if resultats else []

    # resultat[(id, verificateur)] = etat
    etat = {}
    detail = {}
    if resultats:
        for r in resultats["results"]:
            etat[(r["id"], r["verifier"])] = r["etat"]
            detail[(r["id"], r["verifier"])] = r.get("detail", "")

    L: list[str] = []
    A = L.append

    A("# Matrice de couverture du corpus de conformité Evidence")
    A("")
    A("**Corpus `%s`** · %d cas · %d familles · généré par "
      "`conformance/runners/matrix.py`" %
      (version, len(fiches), len({f["family"] for f in fiches})))
    A("")
    if resultats:
        A("Résultats mesurés sur : %s%s" %
          (", ".join("`%s`" % v for v in verificateurs),
           " (mode `--strict`)" if resultats.get("strict") else ""))
    else:
        A("⚠️ **Aucun résultat fourni** : seule la couverture déclarative "
          "est rendue.")
    A("")
    A("---")
    A("")

    # ---- 1. le dénominateur, d'abord -----------------------------------
    A("## 1. Les dénominateurs, avant tout chiffre")
    A("")
    A("| Vérificateur | Périmètre annoncé | Cas applicables | sur %d |"
      % len(fiches))
    A("|---|---|---|---|")
    perimetres = {"python": "soumission, archive, attestation",
                  "rust-core": "**soumission seulement**",
                  "rust-crypto": "**archive et attestation seulement**"}
    applicables = {}
    for v in verificateurs:
        n = sum(1 for f in fiches
                if etat.get((f["id"], v)) not in (None, "NOT APPLICABLE"))
        applicables[v] = n
        A("| `%s` | %s | **%d** | %d |"
          % (v, perimetres.get(v, "?"), n, len(fiches)))
    A("")
    A("> Un cas hors du périmètre d'un vérificateur rend `NOT APPLICABLE`, "
      "jamais `FAIL`. Reprocher à un outil de ne pas faire ce qu'il "
      "n'annonce pas serait une mesure fausse — et gonflerait artificiellement "
      "le dénominateur de l'autre.")
    A("")

    # ---- 2. par famille -------------------------------------------------
    A("## 2. Couverture par famille")
    A("")
    entete = "| Famille | Cas | " + " | ".join(
        "`%s`" % v for v in verificateurs) + " |"
    A(entete)
    A("|---" * (2 + len(verificateurs)) + "|")
    for fam in sorted({f["family"] for f in fiches}):
        cas_fam = [f for f in fiches if f["family"] == fam]
        cellules = []
        for v in verificateurs:
            c = Counter(etat.get((f["id"], v), "—") for f in cas_fam)
            cellules.append(" ".join("%s=%d" % (k, c[k]) for k in sorted(c)))
        A("| **%s** | %d | %s |" % (fam, len(cas_fam), " | ".join(cellules)))
    A("")

    # ---- 3. par statut de règle ----------------------------------------
    A("## 3. Statut des règles citées")
    A("")
    A("| Statut | Cas | Ce que le corpus en fait |")
    A("|---|---|---|")
    sens = {
        "NORMATIVE": "le contrat tranche : un verdict unique est attendu, et "
                     "un écart est un **échec de conformité**",
        "AMBIGUOUS": "le contrat ne tranche pas : le corpus **consigne** les "
                     "comportements observés et **ne déclare personne "
                     "fautif**",
        "EXTENSION": "comportement proposé, non encore normalisé : aucun "
                     "verdict n'est imposé",
    }
    for s in sorted({f["rule"]["statut"] for f in fiches}):
        n = sum(1 for f in fiches if f["rule"]["statut"] == s)
        A("| **%s** | %d | %s |" % (s, n, sens.get(s, "—")))
    A("")

    # ---- 4. la matrice, cas par cas ------------------------------------
    A("## 4. La matrice, cas par cas")
    A("")
    A("`attendu` est la valeur **écrite dans la fiche avant toute "
      "exécution**. Pour un cas ambigu, aucun verdict n'est imposé.")
    A("")
    entete = ("| Cas | Sujet | Règle | Attendu | "
              + " | ".join("`%s`" % v for v in verificateurs) + " |")
    A(entete)
    A("|---" * (4 + len(verificateurs)) + "|")
    for f in fiches:
        at = f["expected"]
        if at.get("ambiguous"):
            attendu = "*(ambigu)*"
        else:
            bouts = []
            if at.get("verdict"):
                bouts.append(at["verdict"])
            if "attested_level" in at:
                bouts.append("niveau=%s" % (at["attested_level"] or "aucun"))
            if at.get("ceiling"):
                bouts.append("**PLAFOND**")
            attendu = " / ".join(bouts) or "—"
        cellules = [etat.get((f["id"], v), "—") for v in verificateurs]
        A("| `%s` | %s | %s | %s | %s |"
          % (f["id"], f["subject"], f["rule"]["statut"], attendu,
             " | ".join(cellules)))
    A("")

    # ---- 5. les règles citées, et leur référence ------------------------
    A("## 5. Les règles citées, et où les lire")
    A("")
    A("Une règle **non citée ici n'est pas couverte**. C'est la lecture la "
      "plus importante de ce document.")
    A("")
    par_reference = defaultdict(list)
    for f in fiches:
        par_reference[f["rule"]["reference"]].append(f["id"])
    A("| Référence normative | Statut | Cas |")
    A("|---|---|---|")
    for ref in sorted(par_reference):
        ids = par_reference[ref]
        statuts = {par_id[i]["rule"]["statut"] for i in ids}
        A("| %s | %s | %s |"
          % (ref.replace("|", "\\|"), ", ".join(sorted(statuts)),
             ", ".join("`%s`" % i for i in ids)))
    A("")

    # ---- 6. les comportements propres à une implémentation --------------
    A("## 6. Comportements propres à une implémentation")
    A("")
    propres = [f for f in fiches if f.get("expected_by_verifier")]
    if propres:
        A("| Cas | Vérificateur | Attente surchargée | Raison déclarée |")
        A("|---|---|---|---|")
        for f in propres:
            for v, sur in f["expected_by_verifier"].items():
                A("| `%s` | `%s` | %s | %s |"
                  % (f["id"], v,
                     ", ".join("%s=%s" % (k, x) for k, x in sur.items()
                               if k != "raison"),
                     sur.get("raison", "—").replace("|", "\\|")))
    else:
        A("Aucun.")
    A("")
    A("> Une surcharge n'est **pas une tolérance** : c'est une différence de "
      "**surface** entre deux outils, déclarée avec sa raison. "
      "`verify_attestation.py` rend un *niveau* ; "
      "`evidence-verify-crypto` rend un *verdict* **et** un niveau, et son "
      "verdict devient `INCOMPLET` quand une ligne requise n'est pas "
      "démontrée — ce que Python ne modélise pas.")
    A("")

    # ---- 7. les cas ambigus, nommément ---------------------------------
    A("## 7. Les cas ambigus, et ce qu'ils consignent")
    A("")
    ambigus = [f for f in fiches if f["expected"].get("ambiguous")]
    A("| Cas | Ambiguïté | Comportements déclarés | Divergent ? |")
    A("|---|---|---|---|")
    divergents = 0
    for f in ambigus:
        at = f["expected"]
        obs, verdicts = [], set()
        for v in ("python", "rust-core", "rust-crypto"):
            if isinstance(at.get(v), dict):
                obs.append("`%s`→%s" % (v, at[v].get("verdict")))
                verdicts.add(at[v].get("verdict"))
        diverge = len(verdicts) > 1
        divergents += 1 if diverge else 0
        A("| `%s` | %s | %s | %s |"
          % (f["id"], f["description"].split(".")[0].replace("|", "\\|"),
             ", ".join(obs) or "*non déclarés*",
             "**OUI**" if diverge else ("non" if obs else "—")))
    A("")
    A("**%d des %d cas ambigus DIVERGENT** : deux vérificateurs honnêtes, un "
      "seul fichier, deux verdicts. C'est ce qu'une ambiguïté normative "
      "produit de dangereux, et c'est pour cela que le corpus la fige "
      "vérificateur par vérificateur plutôt que de la résumer en « ambigu »."
      % (divergents, len(ambigus)))
    A("")
    A("> Jusqu'au corpus 1.1.0, trois de ces lignes portaient *non "
      "déclarés* — et le banc, qui mesurait pourtant les deux verdicts, ne "
      "les comparait jamais. La divergence de `G-07` était dans la donnée et "
      "invisible partout. Corrigé en 1.2.0.")
    A("")
    A("> **Aucun de ces cas ne déclare une implémentation fautive.** Le "
      "contrat ne permet pas de trancher ; le corpus le dit, et s'arrête là.")
    A("")

    # ---- 8. plafonds déclarés ------------------------------------------
    A("## 8. Plafonds déclarés — les cas où une ACCEPTATION est correcte")
    A("")
    plafonds = [f for f in fiches if f["expected"].get("ceiling")]
    A("| Cas | Pourquoi l'acceptation est correcte |")
    A("|---|---|")
    for f in plafonds:
        A("| `%s` | %s |" % (f["id"], f["rule"]["texte"][:200].replace("|", "\\|")))
    A("")
    A("> 🔴 **Ne jamais convertir ces cas en `FAIL` pour améliorer un taux "
      "de détection.** Un paquet réécrit puis re-haché proprement *est* "
      "cohérent avec son manifeste ; l'accepter est la réponse juste, et le "
      "refuser serait une mesure fausse.")
    A("")

    # ---- 9. régressions et échecs déclarés ------------------------------
    A("## 9. Échecs déclarés et régressions")
    A("")
    if resultats:
        connus = resultats.get("known_failures_observed", [])
        echecs = resultats.get("failures", [])
        erreurs = resultats.get("errors", [])
        A("| | Nombre | Lecture |")
        A("|---|---|---|")
        A("| échecs **déclarés** observés | %d | visibles, et **non** comptés "
          "comme régression |" % len(connus))
        A("| échecs **non déclarés** | **%d** | une régression, et la CI "
          "échoue |" % len(echecs))
        A("| erreurs techniques | %d | une conclusion impossible, jamais un "
          "verdict |" % len(erreurs))
        A("| écarts de **code** sur verdict concordant | %d | rapportés à "
          "part : un code peut légitimement différer |"
          % len(resultats.get("code_mismatches", [])))
        A("")
        if connus:
            A("Les échecs déclarés :")
            A("")
            for c in connus:
                A("- `%s` sur `%s`" % (c["id"], c["verifier"]))
            A("")
    else:
        A("*(aucun résultat fourni)*")
        A("")

    # ---- 10. ce que la matrice ne dit pas -------------------------------
    A("## 10. Ce que cette matrice ne dit pas")
    A("")
    A("| | |")
    A("|---|---|")
    A("| **la couverture du protocole** | %d cas citent %d références "
      "normatives. Les contrats Evidence en comportent davantage : ce qui "
      "n'est pas cité en §5 n'est **pas couvert** |"
      % (len(fiches), len(par_reference)))
    A("| **l'exhaustivité** | un corpus n'est jamais exhaustif, et celui-ci "
      "a été écrit par une seule personne |")
    A("| **la vérité des événements** | aucun cas ne la mesure, et aucun ne "
      "peut la mesurer |")
    A("| **l'absence de défaut commun** | deux implémentations qui "
      "concordent ont le même périmètre d'erreur résiduel |")
    A("| **la conformité réglementaire** | aucune norme n'est invoquée, et "
      "aucune n'est satisfaite par construction |")
    A("")
    A("**Aucun pourcentage de « conformité » n'est publié dans ce "
      "document.** Les comptes y sont absolus, avec leur dénominateur, "
      "parce qu'un taux calculé sur un corpus partiel se lirait comme un "
      "taux sur le protocole.")
    A("")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", default=None,
                    help="le rapport JSON de run.py")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    fiches = charger_fiches()
    resultats = json.loads(Path(a.results).read_bytes()) if a.results else None
    texte = rendre(fiches, resultats)
    if a.out:
        Path(a.out).write_text(texte, encoding="utf-8", newline="\n")
        print("matrice ecrite : %s (%d lignes)" % (a.out, texte.count("\n")))
    else:
        print(texte)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
