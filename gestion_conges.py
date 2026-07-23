# -*- coding: utf-8 -*-
"""
Gestion des Congés Payés
========================
Outil graphique (Tkinter) permettant de :
  - Saisir un solde de congés initial.
  - Configurer une acquisition automatique (ex : +2,5 jours / mois).
  - Poser une ou plusieurs périodes de congés.
  - Exclure automatiquement les week-ends et les jours fériés (France)
    du décompte des jours posés.

Aucune dépendance externe : uniquement la bibliothèque standard Python.
Lancement :  python gestion_conges.py
"""

import calendar
import json
import os
import tkinter as tk
from datetime import date, timedelta
from tkinter import messagebox, ttk

MOIS_FR = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]
JOURS_FR = ["Lu", "Ma", "Me", "Je", "Ve", "Sa", "Di"]
FORMAT_FR = "%d-%m-%Y"

FICHIER_DONNEES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conges_data.json")


# ---------------------------------------------------------------------------
#  Logique métier
# ---------------------------------------------------------------------------
def paques(annee: int) -> date:
    """Retourne la date du dimanche de Pâques (algorithme de Butcher / Gauss)."""
    a = annee % 19
    b = annee // 100
    c = annee % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mois = (h + l - 7 * m + 114) // 31
    jour = ((h + l - 7 * m + 114) % 31) + 1
    return date(annee, mois, jour)


def jours_feries_france(annee: int) -> dict:
    """Retourne un dictionnaire {date: nom} des jours fériés français d'une année."""
    p = paques(annee)
    feries = {
        date(annee, 1, 1): "Jour de l'An",
        p + timedelta(days=1): "Lundi de Pâques",
        date(annee, 5, 1): "Fête du Travail",
        date(annee, 5, 8): "Victoire 1945",
        p + timedelta(days=39): "Ascension",
        p + timedelta(days=50): "Lundi de Pentecôte",
        date(annee, 7, 14): "Fête Nationale",
        date(annee, 8, 15): "Assomption",
        date(annee, 11, 1): "Toussaint",
        date(annee, 11, 11): "Armistice 1918",
        date(annee, 12, 25): "Noël",
    }
    return feries


def est_ferie(jour: date) -> bool:
    return jour in jours_feries_france(jour.year)


def est_weekend(jour: date) -> bool:
    return jour.weekday() >= 5  # 5 = samedi, 6 = dimanche


def jours_ouvres_periode(debut: date, fin: date, exclure_weekends: bool = True):
    """
    Parcourt la période [debut, fin] incluse et renvoie :
      (liste des jours décomptés, liste des jours exclus avec leur motif)
    """
    if fin < debut:
        debut, fin = fin, debut

    decomptes = []
    exclus = []
    jour = debut
    while jour <= fin:
        if exclure_weekends and est_weekend(jour):
            exclus.append((jour, "Week-end"))
        elif est_ferie(jour):
            nom = jours_feries_france(jour.year)[jour]
            exclus.append((jour, f"Férié : {nom}"))
        else:
            decomptes.append(jour)
        jour += timedelta(days=1)
    return decomptes, exclus


# ---------------------------------------------------------------------------
#  Widget : sélecteur de date (calendrier déroulant, format DD-MM-AAAA)
# ---------------------------------------------------------------------------
class SelecteurDate(ttk.Frame):
    """Champ de date en lecture seule accompagné d'un petit calendrier.

    Aucune dépendance externe : le calendrier est un simple Toplevel Tkinter.
    L'affichage se fait au format français DD-MM-AAAA.
    """

    def __init__(self, master, date_initiale=None, **kwargs):
        super().__init__(master, **kwargs)
        self._date = date_initiale
        self._popup = None
        self._annee = (date_initiale or date.today()).year
        self._mois = (date_initiale or date.today()).month

        self.var = tk.StringVar()
        self.entry = ttk.Entry(self, width=12, textvariable=self.var, state="readonly")
        self.entry.pack(side="left")
        self.bouton = ttk.Button(self, text="📅", width=3, command=self._basculer)
        self.bouton.pack(side="left", padx=(2, 0))

        if date_initiale is not None:
            self.set_date(date_initiale)

    # --- API publique ---
    def get_date(self):
        return self._date

    def set_date(self, d):
        self._date = d
        self.var.set(d.strftime(FORMAT_FR) if d else "")

    def effacer(self):
        self._date = None
        self.var.set("")

    # --- Gestion du popup ---
    def _basculer(self):
        if self._popup is not None:
            self._fermer()
            return
        base = self._date or date.today()
        self._annee, self._mois = base.year, base.month

        self._popup = tk.Toplevel(self)
        self._popup.title("Choisir une date")
        self._popup.resizable(False, False)
        self._popup.transient(self.winfo_toplevel())
        self._popup.geometry(f"+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height()}")
        self._popup.protocol("WM_DELETE_WINDOW", self._fermer)

        self._cadre = ttk.Frame(self._popup, padding=6)
        self._cadre.pack()
        self._dessiner()

    def _fermer(self):
        if self._popup is not None:
            self._popup.destroy()
            self._popup = None

    def _naviguer(self, delta):
        m = self._mois - 1 + delta
        self._annee += m // 12
        self._mois = m % 12 + 1
        self._dessiner()

    def _dessiner(self):
        for w in self._cadre.winfo_children():
            w.destroy()

        # En-tête : navigation mois / année
        entete = ttk.Frame(self._cadre)
        entete.grid(row=0, column=0, columnspan=7, sticky="ew", pady=(0, 4))
        entete.columnconfigure(1, weight=1)
        ttk.Button(entete, text="◀", width=3, command=lambda: self._naviguer(-1)).grid(row=0, column=0)
        ttk.Label(
            entete, text=f"{MOIS_FR[self._mois - 1]} {self._annee}",
            anchor="center", font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=1, sticky="ew")
        ttk.Button(entete, text="▶", width=3, command=lambda: self._naviguer(1)).grid(row=0, column=2)

        # En-têtes des jours de la semaine
        for i, j in enumerate(JOURS_FR):
            ttk.Label(
                self._cadre, text=j, anchor="center", font=("Segoe UI", 9, "bold")
            ).grid(row=1, column=i, padx=1, pady=1)

        # Grille des jours
        cal = calendar.Calendar(firstweekday=0)  # 0 = lundi
        aujourdhui = date.today()
        for r, semaine in enumerate(cal.monthdatescalendar(self._annee, self._mois), start=2):
            for c, jour in enumerate(semaine):
                if jour.month != self._mois:
                    ttk.Label(self._cadre, text="").grid(row=r, column=c)
                    continue
                btn = tk.Button(
                    self._cadre, text=str(jour.day), width=3, relief="flat",
                    command=lambda d=jour: self._choisir(d),
                )
                if jour == aujourdhui:
                    btn.config(bg="#d6eaff")
                if self._date and jour == self._date:
                    btn.config(bg="#1e824c", fg="white")
                btn.grid(row=r, column=c, padx=1, pady=1)

    def _choisir(self, d):
        self.set_date(d)
        self._fermer()


# ---------------------------------------------------------------------------
#  Application graphique
# ---------------------------------------------------------------------------
class AppConges(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestion des Congés Payés")
        self.geometry("760x640")
        self.minsize(720, 600)

        # État applicatif
        self.solde_initial = 0.0
        self.acquisition_mensuelle = 2.5
        self.date_debut_acquisition = date.today().replace(day=1)
        self.exclure_weekends = tk.BooleanVar(value=True)
        self.periodes = []  # liste de dicts : {debut, fin, jours, exclus}

        self._charger()
        self._construire_ui()
        self._rafraichir()

    # ------------------------- Construction de l'UI -----------------------
    def _construire_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self._onglet_solde(notebook)
        self._onglet_pose(notebook)
        self._onglet_feries(notebook)

        # Barre de résumé en bas
        self.lbl_resume = ttk.Label(
            self, text="", font=("Segoe UI", 11, "bold"), anchor="center"
        )
        self.lbl_resume.pack(fill="x", padx=10, pady=(0, 10))

    def _onglet_solde(self, notebook):
        frame = ttk.Frame(notebook, padding=15)
        notebook.add(frame, text="  Solde & Acquisition  ")

        ttk.Label(frame, text="Solde initial (jours) :").grid(row=0, column=0, sticky="w", pady=6)
        self.ent_solde = ttk.Entry(frame, width=12)
        self.ent_solde.insert(0, self._fmt(self.solde_initial))
        self.ent_solde.grid(row=0, column=1, sticky="w", pady=6, padx=6)

        ttk.Separator(frame, orient="horizontal").grid(
            row=1, column=0, columnspan=3, sticky="ew", pady=12
        )

        ttk.Label(frame, text="Acquisition automatique", font=("Segoe UI", 10, "bold")).grid(
            row=2, column=0, columnspan=3, sticky="w"
        )

        ttk.Label(frame, text="Jours acquis par mois :").grid(row=3, column=0, sticky="w", pady=6)
        self.ent_acq = ttk.Entry(frame, width=12)
        self.ent_acq.insert(0, self._fmt(self.acquisition_mensuelle))
        self.ent_acq.grid(row=3, column=1, sticky="w", pady=6, padx=6)

        ttk.Label(frame, text="Depuis le (AAAA-MM-JJ) :").grid(row=4, column=0, sticky="w", pady=6)
        self.ent_acq_date = ttk.Entry(frame, width=15)
        self.ent_acq_date.insert(0, self.date_debut_acquisition.isoformat())
        self.ent_acq_date.grid(row=4, column=1, sticky="w", pady=6, padx=6)

        ttk.Label(
            frame,
            text="Les congés acquis s'ajoutent au solde initial pour chaque\n"
            "mois complet écoulé depuis la date indiquée.",
            foreground="#555",
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(4, 12))

        ttk.Button(frame, text="Enregistrer", command=self._enregistrer_solde).grid(
            row=6, column=0, sticky="w", pady=8
        )

        self.lbl_detail_solde = ttk.Label(frame, text="", foreground="#0a6")
        self.lbl_detail_solde.grid(row=7, column=0, columnspan=3, sticky="w", pady=8)

    def _onglet_pose(self, notebook):
        frame = ttk.Frame(notebook, padding=15)
        notebook.add(frame, text="  Poser des congés  ")

        saisie = ttk.Frame(frame)
        saisie.pack(fill="x")

        ttk.Label(saisie, text="Du (JJ-MM-AAAA) :").grid(row=0, column=0, sticky="w", pady=6)
        self.sel_debut = SelecteurDate(saisie)
        self.sel_debut.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(saisie, text="Au (JJ-MM-AAAA) :").grid(row=0, column=2, sticky="w", padx=(12, 0))
        self.sel_fin = SelecteurDate(saisie)
        self.sel_fin.grid(row=0, column=3, sticky="w", padx=6)

        ttk.Checkbutton(
            saisie, text="Exclure les week-ends", variable=self.exclure_weekends
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=4)

        ttk.Button(saisie, text="Ajouter la période", command=self._ajouter_periode).grid(
            row=1, column=3, sticky="e", pady=4
        )

        ttk.Label(
            frame,
            text="Astuce : cliquez sur 📅 pour choisir une date. Pour poser un seul "
            "jour, sélectionnez la même date dans les deux champs.",
            foreground="#555",
        ).pack(anchor="w", pady=(2, 8))

        # Tableau des périodes
        cols = ("debut", "fin", "jours", "exclus")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", height=10)
        self.tree.heading("debut", text="Début")
        self.tree.heading("fin", text="Fin")
        self.tree.heading("jours", text="Jours décomptés")
        self.tree.heading("exclus", text="Jours exclus (WE / fériés)")
        self.tree.column("debut", width=100, anchor="center")
        self.tree.column("fin", width=100, anchor="center")
        self.tree.column("jours", width=110, anchor="center")
        self.tree.column("exclus", width=320, anchor="w")
        self.tree.pack(fill="both", expand=True, pady=6)

        ttk.Button(frame, text="Supprimer la période sélectionnée", command=self._supprimer_periode).pack(
            anchor="w", pady=4
        )

    def _onglet_feries(self, notebook):
        frame = ttk.Frame(notebook, padding=15)
        notebook.add(frame, text="  Jours fériés  ")

        top = ttk.Frame(frame)
        top.pack(fill="x")
        ttk.Label(top, text="Année :").pack(side="left")
        self.ent_annee = ttk.Entry(top, width=8)
        self.ent_annee.insert(0, str(date.today().year))
        self.ent_annee.pack(side="left", padx=6)
        ttk.Button(top, text="Afficher", command=self._afficher_feries).pack(side="left")

        cols = ("date", "nom")
        self.tree_feries = ttk.Treeview(frame, columns=cols, show="headings", height=14)
        self.tree_feries.heading("date", text="Date")
        self.tree_feries.heading("nom", text="Jour férié")
        self.tree_feries.column("date", width=140, anchor="center")
        self.tree_feries.column("nom", width=280, anchor="w")
        self.tree_feries.pack(fill="both", expand=True, pady=10)

        self._afficher_feries()

    # ----------------------------- Actions --------------------------------
    def _enregistrer_solde(self):
        try:
            self.solde_initial = float(self.ent_solde.get().replace(",", "."))
            self.acquisition_mensuelle = float(self.ent_acq.get().replace(",", "."))
            self.date_debut_acquisition = date.fromisoformat(self.ent_acq_date.get().strip())
        except ValueError:
            messagebox.showerror("Erreur", "Vérifiez les valeurs saisies (nombres et date AAAA-MM-JJ).")
            return
        self._sauvegarder()
        self._rafraichir()
        acquis = self._conges_acquis()
        self.lbl_detail_solde.config(
            text=f"Solde enregistré. Congés acquis à ce jour : +{self._fmt(acquis)} jours."
        )

    def _ajouter_periode(self):
        debut = self.sel_debut.get_date()
        fin = self.sel_fin.get_date()
        if debut is None or fin is None:
            messagebox.showerror(
                "Erreur", "Veuillez sélectionner une date de début et une date de fin."
            )
            return

        decomptes, exclus = jours_ouvres_periode(debut, fin, self.exclure_weekends.get())
        if not decomptes:
            messagebox.showwarning(
                "Aucun jour décompté",
                "Cette période ne contient que des week-ends et/ou des jours fériés.\n"
                "Aucun jour de congé ne sera décompté.",
            )

        nb_jours = len(decomptes)
        if nb_jours > self._solde_disponible():
            if not messagebox.askyesno(
                "Solde insuffisant",
                f"Cette période décompte {nb_jours} jour(s) mais votre solde "
                f"disponible est de {self._fmt(self._solde_disponible())} jour(s).\n\n"
                "Ajouter quand même ?",
            ):
                return

        self.periodes.append(
            {
                "debut": debut.isoformat(),
                "fin": fin.isoformat(),
                "jours": nb_jours,
                "exclus": [f"{d.strftime(FORMAT_FR)} ({motif})" for d, motif in exclus],
            }
        )
        self._sauvegarder()
        self._rafraichir()
        self.sel_debut.effacer()
        self.sel_fin.effacer()

    def _supprimer_periode(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Sélectionnez d'abord une période dans le tableau.")
            return
        index = self.tree.index(sel[0])
        del self.periodes[index]
        self._sauvegarder()
        self._rafraichir()

    def _afficher_feries(self):
        try:
            annee = int(self.ent_annee.get().strip())
        except ValueError:
            messagebox.showerror("Erreur", "Année invalide.")
            return
        for item in self.tree_feries.get_children():
            self.tree_feries.delete(item)
        for jour, nom in sorted(jours_feries_france(annee).items()):
            self.tree_feries.insert("", "end", values=(jour.strftime("%d/%m/%Y"), nom))

    # ----------------------------- Calculs --------------------------------
    def _conges_acquis(self) -> float:
        """Nombre de jours acquis depuis la date de début d'acquisition (mois complets)."""
        today = date.today()
        deb = self.date_debut_acquisition
        if today < deb:
            return 0.0
        mois = (today.year - deb.year) * 12 + (today.month - deb.month)
        if today.day < deb.day:
            mois -= 1
        mois = max(0, mois)
        return round(mois * self.acquisition_mensuelle, 2)

    def _total_pose(self) -> int:
        return sum(p["jours"] for p in self.periodes)

    def _solde_total(self) -> float:
        return round(self.solde_initial + self._conges_acquis(), 2)

    def _solde_disponible(self) -> float:
        return round(self._solde_total() - self._total_pose(), 2)

    # --------------------------- Rafraîchissement -------------------------
    def _rafraichir(self):
        # Tableau des périodes
        if hasattr(self, "tree"):
            for item in self.tree.get_children():
                self.tree.delete(item)
            for p in self.periodes:
                exclus_txt = ", ".join(p["exclus"]) if p["exclus"] else "—"
                debut_fr = date.fromisoformat(p["debut"]).strftime(FORMAT_FR)
                fin_fr = date.fromisoformat(p["fin"]).strftime(FORMAT_FR)
                self.tree.insert(
                    "", "end",
                    values=(debut_fr, fin_fr, p["jours"], exclus_txt),
                )

        # Résumé
        if hasattr(self, "lbl_resume"):
            dispo = self._solde_disponible()
            couleur = "#c0392b" if dispo < 0 else "#1e824c"
            self.lbl_resume.config(
                text=(
                    f"Solde total : {self._fmt(self._solde_total())} j   |   "
                    f"Posés : {self._total_pose()} j   |   "
                    f"Disponible : {self._fmt(dispo)} j"
                ),
                foreground=couleur,
            )

    # ------------------------- Persistance / util -------------------------
    @staticmethod
    def _fmt(valeur: float) -> str:
        """Formatte un nombre en supprimant le .0 inutile."""
        if float(valeur).is_integer():
            return str(int(valeur))
        return str(round(valeur, 2)).replace(".", ",")

    def _sauvegarder(self):
        data = {
            "solde_initial": self.solde_initial,
            "acquisition_mensuelle": self.acquisition_mensuelle,
            "date_debut_acquisition": self.date_debut_acquisition.isoformat(),
            "exclure_weekends": self.exclure_weekends.get(),
            "periodes": self.periodes,
        }
        try:
            with open(FICHIER_DONNEES, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            messagebox.showerror("Erreur", f"Impossible de sauvegarder les données :\n{e}")

    def _charger(self):
        if not os.path.exists(FICHIER_DONNEES):
            return
        try:
            with open(FICHIER_DONNEES, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.solde_initial = float(data.get("solde_initial", 0.0))
            self.acquisition_mensuelle = float(data.get("acquisition_mensuelle", 2.5))
            self.date_debut_acquisition = date.fromisoformat(
                data.get("date_debut_acquisition", date.today().replace(day=1).isoformat())
            )
            self.exclure_weekends = tk.BooleanVar(value=data.get("exclure_weekends", True))
            self.periodes = data.get("periodes", [])
        except (OSError, ValueError, json.JSONDecodeError):
            pass  # Fichier corrompu : on repart de zéro


if __name__ == "__main__":
    app = AppConges()
    app.mainloop()
