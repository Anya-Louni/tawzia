"""
core/sector_features.py
-----------------------
Une fonctionnalité propre à chaque secteur.

Changing "Type d'activité" must change what the app *does*, not just the volume
numbers. This module gives every sector its own signature analysis , the one
computation that a manager in that sector actually cares about , built on the
same real Algerian cost stack, calendar and forecast as the rest of the app.

    Hub e-commerce       -> Trésorerie COD & exposition aux retours
    Assistance aéroport  -> Vague diaspora & pointe passagers
    Distribution retail  -> Vague Ramadan / pré-Aïd (renfort de picking)
    Hôtellerie           -> Charge ménage selon l'occupation
    Transport & flotte   -> Conformité temps de conduite
    Établissement scolaire -> Calendrier scolaire & encadrement (examens)

Each `compute()` returns a `SectorFeature` the page renders identically, so the
UI stays simple while the content is genuinely different per sector. Everything
is grounded: market figures come from core/sources (cited), the labour figures
from core/labour_dz, the demand from the same forecast the dashboard uses.
"""

from __future__ import annotations

import datetime as _dt
import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from . import labour_dz, sources


# ---------------------------------------------------------------------------
# Result contract
# ---------------------------------------------------------------------------

@dataclass
class SectorFeature:
    key: str
    title: str
    icon: str
    intro: str
    metrics: list = field(default_factory=list)     # (label, display, help)
    table: Optional[pd.DataFrame] = None
    table_caption: str = ""
    chart: Optional[pd.DataFrame] = None            # indexed df for st.*_chart
    chart_kind: str = "bar"
    insight: str = ""
    notes: list = field(default_factory=list)       # citations / assumptions


SIGNATURES = {
    "ecom_hub": {"title": "Trésorerie COD & retours", "icon": ":material/payments:",
                 "intro": "Dans un marché à ~95% payé à la livraison, chaque colis "
                          "sorti transporte des espèces et un risque de retour. "
                          "Voici la trésorerie COD encaissée, les retours attendus "
                          "et la valeur immobilisée sur l'horizon."},
    "airport_ground": {"title": "Vague diaspora & pointe passagers",
                       "icon": ":material/flight_takeoff:",
                       "intro": "L'aéroport algérien vit au rythme du retour de la "
                                "diaspora l'été , un pic que tout modèle calé sur "
                                "l'Europe lit comme un creux. Voici la pointe "
                                "passagers et l'effectif d'enregistrement au pic."},
    "retail_dc": {"title": "Vague Ramadan & pré-Aïd", "icon": ":material/local_grocery_store:",
                  "intro": "La distribution alimentaire est la plus exposée au "
                           "Ramadan : la charge se concentre sur les premiers jours "
                           "du mois et avant l'Aïd. Voici le renfort de picking à "
                           "pré-réserver et quand."},
    "hotel": {"title": "Charge ménage selon l'occupation", "icon": ":material/bed:",
              "intro": "L'occupation pilote tout l'étage : chambres à faire, "
                       "vague de départs, pic week-end. Voici les femmes/valets de "
                       "chambre et réceptionnistes à aligner sur l'occupation "
                       "prévue."},
    "transport": {"title": "Conformité temps de conduite", "icon": ":material/local_shipping:",
                  "intro": "Les chauffeurs sont bornés par une limite quotidienne "
                           "de conduite. Voici les heures de conduite requises, "
                           "l'effectif de chauffeurs pour rester dans les limites, "
                           "et les jours de surchauffe (pré-Aïd) à renforcer."},
    "school": {"title": "Calendrier scolaire & encadrement", "icon": ":material/school:",
               "intro": "L'établissement suit le calendrier scolaire algérien, pas "
                        "le marché : la rentrée est le pic, les vacances vident le "
                        "site, et les examens (BEM/BAC) exigent un renfort de "
                        "surveillance. Voici la phase en cours et l'encadrement."},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dzd(n: float) -> str:
    if abs(n) >= 1e6:
        return f"{n / 1e6:,.2f} M DZD"
    if abs(n) >= 1e3:
        return f"{n / 1e3:,.0f} k DZD"
    return f"{n:,.0f} DZD"


def _ceil(x: float) -> int:
    return int(math.ceil(x)) if x > 0 else 0


def _daily_volume(plan: Optional[dict]) -> pd.DataFrame:
    """Forecast volume aggregated to one row per day, or empty if unavailable."""
    if not plan or "forecast" not in plan:
        return pd.DataFrame(columns=["date", "volume"])
    fc = plan["forecast"]
    if fc is None or fc.empty or "forecast" not in fc.columns:
        return pd.DataFrame(columns=["date", "volume"])
    d = fc.groupby("date", as_index=False)["forecast"].sum().rename(
        columns={"forecast": "volume"})
    d["date"] = pd.to_datetime(d["date"])
    return d.sort_values("date").reset_index(drop=True)


def _shift_hours() -> float:
    return labour_dz.SHIFTS["morning"].hours


def _cite(*keys) -> list:
    out = []
    for k in keys:
        try:
            f = sources.get(k)
            out.append(f"{f.label} : {f.value} {f.unit} , {f.cite()}")
        except Exception:
            pass
    return out


# ---------------------------------------------------------------------------
# Algerian school-year calendar (indicative windows, labelled as such)
# ---------------------------------------------------------------------------

_PHASE_COLOUR = {"cours": "blue", "vacances": "green", "examens": "red", "ete": "orange"}


def school_timeline(as_of: _dt.date) -> list:
    """
    The phases of the Algerian school year containing (or next following)
    `as_of`. Dates are indicative (the Ministry fixes the exact arrêté each
    year); the structure , rentrée, three trimestres, breaks, June exams , is
    stable. Returns ordered dicts: {phase, kind, start, end}.
    """
    # August onward belongs to the upcoming school year (Sept rentrée ahead).
    y = as_of.year if as_of.month >= 8 else as_of.year - 1
    D = _dt.date
    return [
        {"phase": "Vacances d'été", "kind": "ete", "start": D(y, 7, 6), "end": D(y, 9, 20)},
        {"phase": "Rentrée & 1er trimestre", "kind": "cours", "start": D(y, 9, 21), "end": D(y, 11, 1)},
        {"phase": "Vacances d'automne", "kind": "vacances", "start": D(y, 11, 2), "end": D(y, 11, 8)},
        {"phase": "1er trimestre (suite)", "kind": "cours", "start": D(y, 11, 9), "end": D(y, 12, 17)},
        {"phase": "Vacances d'hiver", "kind": "vacances", "start": D(y, 12, 18), "end": D(y + 1, 1, 4)},
        {"phase": "2e trimestre", "kind": "cours", "start": D(y + 1, 1, 5), "end": D(y + 1, 3, 18)},
        {"phase": "Vacances de printemps", "kind": "vacances", "start": D(y + 1, 3, 19), "end": D(y + 1, 4, 5)},
        {"phase": "3e trimestre", "kind": "cours", "start": D(y + 1, 4, 6), "end": D(y + 1, 6, 7)},
        {"phase": "Examens (BEM / BAC)", "kind": "examens", "start": D(y + 1, 6, 8), "end": D(y + 1, 6, 25)},
        {"phase": "Fin d'année & été", "kind": "ete", "start": D(y + 1, 6, 26), "end": D(y + 1, 9, 20)},
    ]


def current_school_phase(as_of: _dt.date) -> dict:
    for ph in school_timeline(as_of):
        if ph["start"] <= as_of <= ph["end"]:
            return ph
    return school_timeline(as_of)[0]


def next_school_event(as_of: _dt.date) -> Optional[dict]:
    future = [ph for ph in school_timeline(as_of) if ph["start"] > as_of]
    return min(future, key=lambda p: p["start"]) if future else None


# ---------------------------------------------------------------------------
# Per-sector signature computations
# ---------------------------------------------------------------------------

def _feat_ecom(plan, people, as_of) -> SectorFeature:
    sig = SIGNATURES["ecom_hub"]
    d = _daily_volume(plan)
    f = SectorFeature("ecom_hub", sig["title"], sig["icon"], sig["intro"])
    if d.empty:
        f.insight = "Prévision indisponible (mode hors-ligne). Réactivez les appels API."
        return f
    aov = sources.value("ecom_avg_order_value_dzd")
    cod = sources.value("cod_share")
    ret = sources.value("cod_return_rate")
    d["cash_cod"] = d["volume"] * cod * aov
    d["retours"] = d["volume"] * ret
    d["immobilise"] = d["retours"] * aov

    peak = d.loc[d["volume"].idxmax()]
    f.metrics = [
        ("Colis (horizon)", f"{d['volume'].sum():,.0f}", "Total prévu sur l'horizon."),
        ("Trésorerie COD / jour", _dzd(d["cash_cod"].mean()),
         "Espèces encaissées par les livreurs en moyenne par jour (à réconcilier)."),
        ("Retours attendus / jour", f"{d['retours'].mean():,.0f}",
         "Colis retournés au taux MENA, à contrôler et remettre en stock."),
        ("Valeur immobilisée (horizon)", _dzd(d["immobilise"].sum()),
         "Valeur bloquée dans les retours , la livraison payée deux fois."),
    ]
    show = d.copy()
    show["date"] = show["date"].dt.strftime("%a %d %b")
    f.table = show.rename(columns={
        "date": "Jour", "volume": "Colis", "cash_cod": "Trésorerie COD (DZD)",
        "retours": "Retours", "immobilise": "Immobilisé (DZD)"})[
        ["Jour", "Colis", "Trésorerie COD (DZD)", "Retours", "Immobilisé (DZD)"]]
    f.table_caption = "Trésorerie et retours par jour, aux paramètres du marché."
    f.chart = d.set_index("date")[["cash_cod"]].rename(columns={"cash_cod": "Trésorerie COD (DZD)"})
    f.chart_kind = "bar"
    f.insight = (f"Jour de pointe le {pd.to_datetime(peak['date']):%d %b} : "
                 f"{_dzd(peak['volume'] * cod * aov)} d'espèces COD à réconcilier "
                 f"et {peak['volume'] * ret:,.0f} retours à traiter , renforcez la "
                 f"caisse et le contrôle retours ce jour-là.")
    f.notes = _cite("cod_share", "cod_return_rate", "ecom_avg_order_value_dzd")
    return f


def _feat_airport(plan, people, as_of) -> SectorFeature:
    sig = SIGNATURES["airport_ground"]
    d = _daily_volume(plan)
    f = SectorFeature("airport_ground", sig["title"], sig["icon"], sig["intro"])
    if d.empty:
        f.insight = "Prévision indisponible (mode hors-ligne)."
        return f
    agent = labour_dz.ROLES["checkin_agent"].productivity_per_hour * _shift_hours()
    d["agents"] = np.ceil(d["volume"] / max(agent, 1)).astype(int)
    peak = d.loc[d["volume"].idxmax()]
    trough = d.loc[d["volume"].idxmin()]
    swing = peak["volume"] / max(trough["volume"], 1)
    f.metrics = [
        ("Passagers (horizon)", f"{d['volume'].sum():,.0f}", "Total prévu sur l'horizon."),
        ("Pointe passagers / jour", f"{peak['volume']:,.0f}",
         f"Jour le plus chargé ({pd.to_datetime(peak['date']):%d %b})."),
        ("Agents d'enregistrement au pic", f"{int(peak['agents'])}",
         "Effectif nécessaire au débit d'enregistrement le jour de pointe."),
        ("Amplitude pic/creux", f"{swing:.1f}×",
         "Écart entre le jour le plus et le moins chargé de l'horizon."),
    ]
    show = d.copy(); show["date"] = show["date"].dt.strftime("%a %d %b")
    f.table = show.rename(columns={"date": "Jour", "volume": "Passagers",
                                   "agents": "Agents check-in"})[
        ["Jour", "Passagers", "Agents check-in"]]
    f.table_caption = "Passagers et effectif d'enregistrement requis par jour."
    f.chart = d.set_index("date")[["volume"]].rename(columns={"volume": "Passagers"})
    f.chart_kind = "area"
    f.insight = ("Le module **Aéroport** (menu Planification en édition aéroport) "
                 "va plus loin : flux passagers heure par heure et cascade de "
                 "retards. La pointe diaspora d'été est le vrai pic annuel.")
    f.notes = _cite("alg_pax_2024", "airalgerie_pax_target_2026")
    return f


def _feat_retail(plan, people, as_of) -> SectorFeature:
    sig = SIGNATURES["retail_dc"]
    d = _daily_volume(plan)
    f = SectorFeature("retail_dc", sig["title"], sig["icon"], sig["intro"])
    if d.empty:
        f.insight = "Prévision indisponible (mode hors-ligne)."
        return f
    prod = labour_dz.ROLES["warehouse_op"].productivity_per_hour * _shift_hours()
    baseline = float(d["volume"].median())
    d["surplus"] = (d["volume"] - baseline).clip(lower=0)
    d["renfort"] = np.ceil(d["surplus"] / max(prod, 1)).astype(int)
    d["pointe"] = d["volume"] >= baseline * 1.25
    surge = d[d["pointe"]]
    peak = d.loc[d["volume"].idxmax()]
    first_surge = surge["date"].min() if not surge.empty else None
    f.metrics = [
        ("Charge médiane / jour", f"{baseline:,.0f}", "Cartons un jour ordinaire."),
        ("Pic de charge", f"{peak['volume']:,.0f}",
         f"Jour le plus chargé ({pd.to_datetime(peak['date']):%d %b})."),
        ("Jours de pointe", f"{int(d['pointe'].sum())}",
         "Jours à ≥ +25% de la médiane sur l'horizon."),
        ("Renfort à pré-réserver", f"{int(d['renfort'].sum())} agents-jours",
         "Agents-jours d'intérim à réserver pour absorber les pointes."),
    ]
    show = d.copy(); show["date"] = show["date"].dt.strftime("%a %d %b")
    show["Pointe"] = np.where(show["pointe"], "● pointe", "")
    f.table = show.rename(columns={"date": "Jour", "volume": "Cartons",
                                   "renfort": "Renfort (agents)"})[
        ["Jour", "Cartons", "Renfort (agents)", "Pointe"]]
    f.table_caption = "Charge, renfort de picking et jours de pointe."
    f.chart = d.set_index("date")[["volume"]].rename(columns={"volume": "Cartons"})
    if first_surge is not None:
        book_by = (pd.to_datetime(first_surge) - pd.Timedelta(days=3))
        f.insight = (f"Première pointe le {pd.to_datetime(first_surge):%d %b} : "
                     f"pré-réservez les intérimaires avant le "
                     f"{book_by:%d %b} (préavis de 3 jours) pour éviter la "
                     f"majoration de dernière minute.")
    else:
        f.insight = ("Aucune pointe marquée sur cet horizon , la charge est "
                     "régulière. Surveillez l'entrée en Ramadan pour le front-load.")
    return f


def _feat_hotel(plan, people, as_of) -> SectorFeature:
    sig = SIGNATURES["hotel"]
    d = _daily_volume(plan)
    f = SectorFeature("hotel", sig["title"], sig["icon"], sig["intro"])
    if d.empty:
        f.insight = "Prévision indisponible (mode hors-ligne)."
        return f
    hk = labour_dz.ROLES["housekeeper"].productivity_per_hour * _shift_hours()
    fd = labour_dz.ROLES["front_desk"].productivity_per_hour * _shift_hours()
    d["menage"] = np.ceil(d["volume"] / max(hk, 1)).astype(int)
    d["reception"] = np.ceil(d["volume"] / max(fd, 1)).astype(int)
    d["weekday"] = d["date"].dt.weekday
    peak = d.loc[d["volume"].idxmax()]
    wk = d[d["weekday"].isin([3, 4])]["volume"].mean()   # Thu-Fri leisure
    wd = d[~d["weekday"].isin([3, 4, 5])]["volume"].mean()
    f.metrics = [
        ("Occupation moyenne", f"{d['volume'].mean():,.0f}", "Chambres occupées / jour."),
        ("Pic d'occupation", f"{peak['volume']:,.0f}",
         f"Jour le plus rempli ({pd.to_datetime(peak['date']):%d %b})."),
        ("Ménage au pic", f"{int(peak['menage'])}",
         "Femmes/valets de chambre nécessaires le jour de pointe."),
        ("Réception au pic", f"{int(peak['reception'])}",
         "Réceptionnistes nécessaires au pic d'arrivées."),
    ]
    show = d.copy(); show["date"] = show["date"].dt.strftime("%a %d %b")
    f.table = show.rename(columns={"date": "Jour", "volume": "Chambres occ.",
                                   "menage": "Ménage", "reception": "Réception"})[
        ["Jour", "Chambres occ.", "Ménage", "Réception"]]
    f.table_caption = "Occupation et effectif d'étage/réception par jour."
    f.chart = d.set_index("date")[["volume"]].rename(columns={"volume": "Chambres occupées"})
    f.chart_kind = "area"
    lift = (wk / wd - 1) * 100 if wd else 0
    sens = "au-dessus de" if lift >= 0 else "sous"
    f.insight = (f"Le week-end de loisir (jeu.-ven.) tourne ~{abs(lift):.0f}% "
                 f"{sens} la semaine : concentrez le ménage sur la vague de "
                 f"départs et renforcez la réception aux arrivées.")
    return f


def _feat_transport(plan, people, as_of) -> SectorFeature:
    sig = SIGNATURES["transport"]
    d = _daily_volume(plan)
    f = SectorFeature("transport", sig["title"], sig["icon"], sig["intro"])
    if d.empty:
        f.insight = "Prévision indisponible (mode hors-ligne)."
        return f
    prod = labour_dz.ROLES["driver"].productivity_per_hour   # trajets / heure
    limit = sources.value("transport_daily_driving_limit_h")
    d["heures_conduite"] = d["volume"] / max(prod, 1)
    d["chauffeurs"] = np.ceil(d["heures_conduite"] / max(limit, 1)).astype(int)
    med = float(d["chauffeurs"].median())
    d["surchauffe"] = d["chauffeurs"] >= med * 1.3
    peak = d.loc[d["volume"].idxmax()]
    f.metrics = [
        ("Heures de conduite / jour", f"{d['heures_conduite'].mean():,.0f} h",
         "Total d'heures de conduite requises en moyenne par jour."),
        ("Chauffeurs requis au pic", f"{int(peak['chauffeurs'])}",
         f"Pour tenir la charge sans dépasser {limit:.0f} h/conducteur "
         f"({pd.to_datetime(peak['date']):%d %b})."),
        ("Limite / conducteur", f"{limit:.0f} h/jour",
         "Plafond de conduite avant repos obligatoire (indicatif)."),
        ("Jours de surchauffe", f"{int(d['surchauffe'].sum())}",
         "Jours à ≥ +30% de l'effectif médian , risque de dépassement/fatigue."),
    ]
    show = d.copy(); show["date"] = show["date"].dt.strftime("%a %d %b")
    show["Surchauffe"] = np.where(show["surchauffe"], "● renfort", "")
    show["heures_conduite"] = show["heures_conduite"].round(0)
    f.table = show.rename(columns={"date": "Jour", "volume": "Trajets",
                                   "heures_conduite": "Heures conduite",
                                   "chauffeurs": "Chauffeurs"})[
        ["Jour", "Trajets", "Heures conduite", "Chauffeurs", "Surchauffe"]]
    f.table_caption = "Trajets, heures de conduite et effectif conforme par jour."
    f.chart = d.set_index("date")[["chauffeurs"]].rename(columns={"chauffeurs": "Chauffeurs requis"})
    f.insight = ("Les jours de surchauffe (typiquement le pré-Aïd) exigent des "
                 "chauffeurs de relève : sans eux, tenir la charge force le "
                 "dépassement des limites de conduite , un risque légal et de "
                 "sécurité, pas seulement un surcoût.")
    f.notes = _cite("transport_daily_driving_limit_h")
    return f


def _feat_school(plan, people, as_of) -> SectorFeature:
    from . import demand as _demand
    sig = SIGNATURES["school"]
    f = SectorFeature("school", sig["title"], sig["icon"], sig["intro"])

    phase = current_school_phase(as_of)
    nxt = next_school_event(as_of)
    students = int(_demand.PROFILES["school"].base_daily_volume)
    spt = sources.value("school_students_per_teacher")
    inv = sources.value("school_students_per_invigilator")
    teachers_needed = _ceil(students / spt)
    invigilators = _ceil(students / inv)
    staff_now = len(people) if people else 0

    days_to = (nxt["start"] - as_of).days if nxt else None
    f.metrics = [
        ("Phase actuelle", phase["phase"], "Position dans l'année scolaire algérienne."),
        ("Prochaine échéance",
         f"{nxt['phase']} (J-{days_to})" if nxt else "—",
         f"Débute le {nxt['start']:%d %b %Y}." if nxt else ""),
        ("Enseignants requis", f"{teachers_needed}",
         f"Pour {students:,} élèves au taux d'encadrement de {spt} élèves/enseignant."),
        ("Surveillants d'examen", f"{invigilators}",
         f"Renfort de surveillance en période BEM/BAC ({inv} élèves/surveillant)."),
    ]

    tl = school_timeline(as_of)
    rows = []
    for ph in tl:
        rows.append({
            "Phase": ph["phase"],
            "Type": {"cours": "Cours", "vacances": "Vacances",
                     "examens": "Examens", "ete": "Été"}[ph["kind"]],
            "Début": ph["start"].strftime("%d %b %Y"),
            "Fin": ph["end"].strftime("%d %b %Y"),
            "En cours": "●" if ph is phase else "",
        })
    f.table = pd.DataFrame(rows)
    f.table_caption = ("Calendrier scolaire algérien (dates indicatives , l'arrêté "
                       "ministériel fixe l'exact chaque année).")

    if phase["kind"] == "examens":
        f.insight = (f"Période d'examens : mobilisez ~{invigilators} surveillants "
                     f"en plus du corps enseignant, et verrouillez les congés du "
                     f"personnel jusqu'à la fin des épreuves.")
    elif phase["kind"] in ("ete", "vacances") and nxt:
        f.insight = (f"Site en {phase['phase'].lower()} : c'est la fenêtre pour "
                     f"recruter et former avant « {nxt['phase']} » (J-{days_to}). "
                     f"Effectif encadrant actuel : {staff_now}, cible ~{teachers_needed}.")
    else:
        gap = teachers_needed - staff_now
        f.insight = (f"En cours : effectif encadrant {staff_now} vs besoin "
                     f"~{teachers_needed} enseignants"
                     + (f" , il manque ~{gap}." if gap > 0 else " , dotation suffisante."))
    f.notes = _cite("school_students_per_teacher", "school_students_per_invigilator")
    return f


_DISPATCH = {
    "ecom_hub": _feat_ecom,
    "airport_ground": _feat_airport,
    "retail_dc": _feat_retail,
    "hotel": _feat_hotel,
    "transport": _feat_transport,
    "school": _feat_school,
}


def has_feature(profile_key: str) -> bool:
    return profile_key in _DISPATCH


def compute(profile_key: str, plan: Optional[dict], people: Optional[list],
            as_of: Optional[_dt.date] = None) -> Optional[SectorFeature]:
    """Compute the signature feature for a sector, or None if unknown."""
    as_of = as_of or _dt.date.today()
    fn = _DISPATCH.get(profile_key)
    if fn is None:
        return None
    return fn(plan, people or [], as_of)


if __name__ == "__main__":
    from . import demand as _d, hr

    print("Sector signature features , self check\n")
    as_of = _dt.date.today()
    # a tiny fake plan: 14 days of volume per sector base
    for key, prof in _d.PROFILES.items():
        dates = pd.date_range(as_of, periods=14, freq="D")
        vol = np.linspace(prof.base_daily_volume * 0.7, prof.base_daily_volume * 1.6, 14)
        fc = pd.DataFrame({"date": np.repeat(dates, 1), "shift": "morning",
                           "forecast": vol})
        people = hr.sample_workforce(prof.primary_role, 30, "Alger")
        feat = compute(key, {"forecast": fc}, people, as_of)
        print(f"— {prof.label}  →  {feat.title}")
        for label, disp, _ in feat.metrics:
            print(f"     {label:<28} {disp}")
        print(f"     » {feat.insight[:110]}")
        print()
