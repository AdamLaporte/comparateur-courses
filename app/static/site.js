// Comportements de l'interface, sans framework. Chargé (defer) sur toutes les pages ;
// chaque partie ne s'active que si ses éléments sont présents. Le site reste utilisable sans ce fichier.
(() => {
  "use strict";

  const moinsDeMouvement = window.matchMedia("(prefers-reduced-motion: reduce)");
  const petitEcran = window.matchMedia("(max-width: 959px)");
  const logo = document.querySelector("[data-grignoter]");
  logo?.addEventListener("click", () => {
    logo.setAttribute("aria-pressed", String(logo.getAttribute("aria-pressed") === "false"));
  });
  const ICONE_VALIDE =
    '<svg class="icone" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>';
  const ICONE_CROIX =
    '<svg class="icone" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>';

  // ------------------------------------------------------------------------------------------------
  // Messages brefs (toasts) : posés par le serveur dans #toasts (hors bande) ou par toast() ci-dessous.
  // Ils partent seuls, après data-duree ms, sauf tant que la souris ou le clavier est dessus.
  // ------------------------------------------------------------------------------------------------
  const zoneToasts = document.getElementById("toasts");

  const fermerToast = (el) => {
    if (!el || el.classList.contains("part")) return;
    el.classList.add("part");
    const retirer = () => el.remove();
    if (moinsDeMouvement.matches) retirer();
    else {
      el.addEventListener("animationend", retirer, { once: true });
      setTimeout(retirer, 400);
    }
  };

  const armerToast = (el) => {
    if (el.dataset.arme) return;
    el.dataset.arme = "1";
    const duree = Number(el.dataset.duree) || 3500;
    el.style.setProperty("--duree-toast", `${duree}ms`);
    let reste = duree;
    let debut = performance.now();
    let minuteur = setTimeout(() => fermerToast(el), reste);
    const pause = () => {
      if (el.classList.contains("en-pause")) return;
      clearTimeout(minuteur);
      reste -= performance.now() - debut;
      el.classList.add("en-pause");
    };
    const reprise = () => {
      if (!el.classList.contains("en-pause")) return;
      debut = performance.now();
      minuteur = setTimeout(() => fermerToast(el), Math.max(reste, 1200));
      el.classList.remove("en-pause");
    };
    el.addEventListener("mouseenter", pause);
    el.addEventListener("mouseleave", reprise);
    el.addEventListener("focusin", pause);
    el.addEventListener("focusout", (e) => {
      if (!el.contains(e.relatedTarget)) reprise();
    });
    el.querySelector(".toast-fermer")?.addEventListener("click", () => fermerToast(el));
    // « Annuler » : le message part une fois la requête finie (htmx a besoin du bouton jusque-là).
    el.addEventListener("htmx:afterRequest", () => fermerToast(el));
    // Pas plus de trois messages à la fois : le plus ancien laisse sa place.
    const messages = zoneToasts.querySelectorAll(".toast:not(.part)");
    if (messages.length > 3) fermerToast(messages[0]);
  };

  const toast = (message, duree = 3200) => {
    if (!zoneToasts) return;
    const el = document.createElement("div");
    el.className = "toast";
    el.dataset.duree = String(duree);
    el.innerHTML = `<span class="toast-icone">${ICONE_VALIDE}</span><p class="toast-texte"></p><button type="button" class="toast-fermer" aria-label="Fermer le message">${ICONE_CROIX}</button><span class="toast-minuteur" aria-hidden="true"></span>`;
    el.querySelector(".toast-texte").textContent = message;
    zoneToasts.append(el);
  };

  if (zoneToasts) {
    zoneToasts.querySelectorAll(".toast").forEach(armerToast);
    new MutationObserver(() => zoneToasts.querySelectorAll(".toast").forEach(armerToast)).observe(zoneToasts, {
      childList: true,
    });
  }

  // ------------------------------------------------------------------------------------------------
  // Formulaires classiques : le bouton montre qu'on attend (et ne part pas deux fois).
  // ------------------------------------------------------------------------------------------------
  document.addEventListener("submit", (e) => {
    const formulaire = e.target;
    if (!(formulaire instanceof HTMLFormElement) || e.defaultPrevented) return;
    if (formulaire.matches("[hx-post], [hx-get], [hx-delete]")) return;
    const bouton = e.submitter || formulaire.querySelector('button[type="submit"], button:not([type])');
    if (bouton) {
      bouton.classList.add("envoi");
      bouton.setAttribute("aria-busy", "true");
    }
  });
  // Retour arrière (cache du navigateur) : les boutons redeviennent normaux.
  window.addEventListener("pageshow", () => {
    document.querySelectorAll(".envoi").forEach((b) => {
      b.classList.remove("envoi");
      b.removeAttribute("aria-busy");
    });
  });

  // ------------------------------------------------------------------------------------------------
  // Mot de passe : bouton « Afficher / Masquer » dans chaque champ.
  // ------------------------------------------------------------------------------------------------
  document.querySelectorAll('input[type="password"]').forEach((champ) => {
    const enveloppe = document.createElement("span");
    enveloppe.className = "champ-mdp";
    champ.parentNode.insertBefore(enveloppe, champ);
    enveloppe.append(champ);
    const bouton = document.createElement("button");
    bouton.type = "button";
    bouton.className = "voir-mdp";
    bouton.textContent = "Afficher";
    bouton.setAttribute("aria-pressed", "false");
    bouton.setAttribute("aria-label", "Afficher le mot de passe");
    bouton.addEventListener("click", () => {
      const visible = champ.type === "password";
      champ.type = visible ? "text" : "password";
      bouton.textContent = visible ? "Masquer" : "Afficher";
      bouton.setAttribute("aria-pressed", String(visible));
      bouton.setAttribute("aria-label", visible ? "Masquer le mot de passe" : "Afficher le mot de passe");
      champ.focus();
    });
    enveloppe.append(bouton);
  });

  // ------------------------------------------------------------------------------------------------
  // Accueil : « Me localiser » remplit le lieu avec la position du navigateur, puis envoie.
  // ------------------------------------------------------------------------------------------------
  document.querySelectorAll("form .panneau-trajet").forEach((panneau) => {
    const actif = panneau.querySelector('[name="trajet"]');
    const mode = panneau.querySelector('[name="mode_trajet"]');
    const rayon = panneau.querySelector('[name="rayon_trajet"]');
    const saisie = panneau.closest("form").querySelector('#code_postal');
    const lieuSaisi = panneau.querySelector('[name="lieu_trajet"][value=""]');
    const actualiser = () => {
      const favori = panneau.querySelector('[name="lieu_trajet"]:checked');
      const choix = mode.value || favori?.dataset.modeFavori || "voiture";
      const option = [...mode.options].find((element) => element.value === choix);
      rayon.placeholder = option.dataset.rayon.replace(".", ",");
      rayon.disabled = !actif.checked;
      mode.disabled = !actif.checked;
    };
    panneau.addEventListener("change", actualiser);
    saisie?.addEventListener("input", () => {
      if (lieuSaisi) lieuSaisi.checked = true;
      actualiser();
    });
    actualiser();
  });

  const boutonLocaliser = document.getElementById("me-localiser");
  if (boutonLocaliser) {
    const champ = document.getElementById("code_postal");
    const erreur = document.getElementById("erreur-lieu");
    const libelle = boutonLocaliser.querySelector("span");
    const texteInitial = libelle ? libelle.textContent : "";

    const signaler = (message) => {
      if (!erreur) return;
      const span = erreur.querySelector("span");
      if (span) span.textContent = message;
      erreur.hidden = false;
    };

    boutonLocaliser.addEventListener("click", () => {
      if (!navigator.geolocation) {
        signaler("Votre navigateur ne permet pas la localisation : saisissez votre ville.");
        return;
      }
      boutonLocaliser.disabled = true;
      boutonLocaliser.classList.add("localise");
      if (libelle) libelle.textContent = "Localisation…";
      navigator.geolocation.getCurrentPosition(
        (position) => {
          champ.value = `${position.coords.latitude.toFixed(5)},${position.coords.longitude.toFixed(5)}`;
          champ.dispatchEvent(new Event("input"));
          if (libelle) libelle.textContent = "Recherche des magasins…";
          champ.form.submit();
        },
        () => {
          boutonLocaliser.disabled = false;
          boutonLocaliser.classList.remove("localise");
          if (libelle) libelle.textContent = texteInitial;
          signaler("Localisation refusée ou impossible : saisissez votre ville ou votre code postal.");
        },
        { timeout: 10000, maximumAge: 300000 },
      );
    });
  }

  // ------------------------------------------------------------------------------------------------
  // Magasins : carte (Leaflet) avec un repère numéroté par magasin, liée à la liste.
  // ------------------------------------------------------------------------------------------------
  const conteneurCarte = document.getElementById("carte-magasins");
  const donneesCarte = document.getElementById("donnees-carte");
  if (conteneurCarte && donneesCarte) {
    const dessinerCarte = () => {
      if (!window.L || conteneurCarte.dataset.prete) return; // Leaflet absent : la liste suffit.
      conteneurCarte.dataset.prete = "1";
      const d = JSON.parse(donneesCarte.textContent);
      const carte = L.map(conteneurCarte, { scrollWheelZoom: false });
      // Tuiles OpenStreetMap standard (sans clé ; usage léger avec attribution), désaturées en CSS.
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">contributeurs OpenStreetMap</a>',
      }).addTo(carte);

      L.marker(d.centre, {
        icon: L.divIcon({ className: "repere repere-vous", html: "<span></span>", iconSize: [18, 18] }),
        title: "Votre lieu",
        keyboard: false,
      }).addTo(carte);
      if (d.rayon_km) {
        L.circle(d.centre, {
          radius: d.rayon_km * 1000,
          color: "#16150f",
          weight: 1,
          dashArray: "4 5",
          fillColor: "#ffd23f",
          fillOpacity: 0.07,
          interactive: false,
        }).addTo(carte);
      }

      const points = [d.centre];
      const reperes = new Map();
      d.magasins.forEach((m) => {
        const enseigne = String(m.enseigne).replace(/[^a-z]/g, "");
        const repere = L.marker([m.lat, m.lon], {
          icon: L.divIcon({ className: `repere ${enseigne}`, html: `<span>${Number(m.n)}</span>`, iconSize: [30, 30] }),
          title: `${m.n}. ${m.nom}`,
          alt: `${m.n}. ${m.nom}`,
        }).addTo(carte);
        reperes.set(String(m.n), repere);
        points.push([m.lat, m.lon]);
      });
      carte.fitBounds(points, { padding: [36, 36], maxZoom: 15 });
      // Les repères n'existent qu'une fois la vue fixée : ils se posent alors dans l'ordre de la liste.
      [...reperes.values()].forEach((repere, i) => {
        repere.getElement()?.querySelector("span")?.style.setProperty("--i", String(i));
      });

      document.querySelectorAll(".liste-magasins li[data-numero]").forEach((li) => {
        const repere = reperes.get(li.dataset.numero);
        if (!repere) return;
        const activer = (oui) => {
          const element = repere.getElement();
          if (element) element.classList.toggle("actif", oui);
          repere.setZIndexOffset(oui ? 1000 : 0);
          li.classList.toggle("survol", oui);
        };
        li.addEventListener("mouseenter", () => activer(true));
        li.addEventListener("mouseleave", () => activer(false));
        repere.on("mouseover", () => activer(true));
        repere.on("mouseout", () => activer(false));
        repere.on("click", () => li.scrollIntoView({ block: "nearest", behavior: "smooth" }));
      });
    };
    if (window.L) dessinerCarte();
    else window.addEventListener("load", dessinerCarte);
  }

  // ------------------------------------------------------------------------------------------------
  // Ma liste
  // ------------------------------------------------------------------------------------------------
  const recherche = document.getElementById("q");
  const viderRecherche = () => {
    if (!recherche) return;
    recherche.value = "";
    recherche.focus();
  };

  // Après un ajout depuis les suggestions : on vide la recherche pour enchaîner l'article suivant.
  document.body.addEventListener("htmx:afterRequest", (e) => {
    const element = e.detail.elt;
    if (e.detail.successful && element && element.closest && element.closest(".suggestion")) viderRecherche();
  });

  // Clavier : Entrée ajoute « le moins cher » de ce qui est tapé, ↓ ↑ parcourent les suggestions.
  if (recherche && window.htmx) {
    const boutonsSuggestions = () => [...document.querySelectorAll("#suggestions .suggestion button")];
    recherche.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.isComposing) {
        e.preventDefault();
        const texte = recherche.value.trim();
        if (texte.length < 2) return;
        const premiere = document.querySelector("#suggestions .suggestion.equivalent form");
        if (premiere && premiere.querySelector('input[name="recherche"]')?.value === texte) {
          premiere.requestSubmit();
        } else {
          htmx.ajax("POST", "/panier/lignes", {
            target: "#liste",
            swap: "outerHTML transition:true",
            values: { mode: "equivalent", recherche: texte, libelle: texte, quantite: "1" },
          });
          viderRecherche();
        }
      } else if (e.key === "ArrowDown") {
        const boutons = boutonsSuggestions();
        if (boutons.length) {
          e.preventDefault();
          boutons[0].focus();
        }
      } else if (e.key === "Escape") {
        const suggestions = document.getElementById("suggestions");
        if (suggestions) suggestions.innerHTML = "";
      }
    });
    document.getElementById("suggestions")?.addEventListener("keydown", (e) => {
      const boutons = boutonsSuggestions();
      const i = boutons.indexOf(document.activeElement);
      if (i < 0) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        boutons[Math.min(i + 1, boutons.length - 1)].focus();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        (i === 0 ? recherche : boutons[i - 1]).focus();
      } else if (e.key === "Escape") {
        recherche.focus();
      }
    });
  }

  // Après chaque changement de la liste : on met en valeur ce qui vient d'arriver ; si la liste n'est pas à
  // l'écran (téléphone), un message le confirme ; et des prix déjà affichés sont marqués « à mettre à jour ».
  let idsAvant = null;
  const idsDeLaListe = () => new Set([...document.querySelectorAll("#liste .lignes > li")].map((li) => li.dataset.id));

  const marquerPrixPerimes = () => {
    const comparaison = document.querySelector(".comparaison");
    if (!comparaison || !comparaison.querySelector(".tableau-prix") || comparaison.classList.contains("perimee")) return;
    comparaison.classList.add("perimee");
    const avis = document.createElement("div");
    avis.className = "avis-perime";
    avis.setAttribute("role", "status");
    avis.innerHTML = '<p>Votre liste a changé : ces prix ne sont plus à jour.</p><button type="button" class="principal">Mettre à jour les prix</button>';
    avis.querySelector("button").addEventListener("click", () => document.getElementById("bouton-comparer")?.click());
    comparaison.prepend(avis);
  };

  document.body.addEventListener("htmx:beforeSwap", (e) => {
    if (e.detail.target && e.detail.target.id === "liste") idsAvant = idsDeLaListe();
  });
  document.body.addEventListener("htmx:afterSwap", (e) => {
    if (!e.detail.target || e.detail.target.id !== "liste" || idsAvant === null) return;
    const nouvelles = [...document.querySelectorAll("#liste .lignes > li")].filter((li) => !idsAvant.has(li.dataset.id));
    idsAvant = null;
    nouvelles.forEach((li) => {
      li.classList.add("nouveau");
      setTimeout(() => li.classList.remove("nouveau"), 1700);
    });
    const liste = document.getElementById("liste");
    const visible = liste && liste.getBoundingClientRect().top < window.innerHeight && liste.getBoundingClientRect().bottom > 0;
    // Le serveur a déjà posé un message pour ce changement (retrait, « Annuler »…) : pas de second.
    const parServeur = zoneToasts && zoneToasts.querySelector(".toast:not([data-vu])");
    if (nouvelles.length && !visible && !parServeur) {
      const total = document.querySelectorAll("#liste .lignes > li").length;
      const nom = nouvelles.length === 1 ? `« ${nouvelles[0].querySelector(".libelle")?.textContent.trim()} » ajouté` : `${nouvelles.length} articles ajoutés`;
      toast(`${nom} · ${total} article${total > 1 ? "s" : ""} dans la liste`);
    }
    zoneToasts?.querySelectorAll(".toast").forEach((t) => (t.dataset.vu = "1"));
    // Toute modification (ajout, retrait, quantité, bascule) rend les prix affichés périmés.
    marquerPrixPerimes();
  });

  // Glisser-déposer une photo de ticket sur la zone prévue (sinon le clic suffit).
  const zoneTicket = document.querySelector(".zone-ticket");
  const champTicket = document.getElementById("image-ticket");
  if (zoneTicket && champTicket) {
    ["dragenter", "dragover"].forEach((nom) =>
      zoneTicket.addEventListener(nom, (e) => {
        e.preventDefault();
        zoneTicket.classList.add("survol");
      }),
    );
    ["dragleave", "drop"].forEach((nom) => zoneTicket.addEventListener(nom, () => zoneTicket.classList.remove("survol")));
    zoneTicket.addEventListener("drop", (e) => {
      e.preventDefault();
      if (!e.dataTransfer || !e.dataTransfer.files.length) return;
      champTicket.files = e.dataTransfer.files;
      champTicket.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  // Téléphone : barre « Comparer » en bas de l'écran quand le vrai bouton n'est pas visible.
  const barre = document.querySelector(".barre-comparer");
  const boutonComparer = document.getElementById("bouton-comparer");
  const resultats = document.getElementById("resultats");
  if (barre && boutonComparer && resultats && "IntersectionObserver" in window) {
    let boutonVisible = true;
    let resultatsVisibles = false;
    const mettreAJour = () => {
      const n = document.querySelectorAll("#liste .lignes > li").length;
      const montrer = petitEcran.matches && n > 0 && !boutonVisible && !resultatsVisibles;
      barre.hidden = !montrer;
      document.body.classList.toggle("avec-barre", montrer);
      const nombre = barre.querySelector(".barre-comparer-nb");
      if (nombre) nombre.textContent = ` · ${n} article${n > 1 ? "s" : ""}`;
    };
    new IntersectionObserver(([entree]) => {
      boutonVisible = entree.isIntersecting;
      mettreAJour();
    }).observe(boutonComparer);
    new IntersectionObserver(([entree]) => {
      resultatsVisibles = entree.isIntersecting && resultats.childElementCount > 0;
      mettreAJour();
    }).observe(resultats);
    barre.querySelector("[data-comparer]")?.addEventListener("click", () => boutonComparer.click());
    document.body.addEventListener("htmx:afterSettle", mettreAJour);
    petitEcran.addEventListener("change", mettreAJour);
  }

  // ------------------------------------------------------------------------------------------------
  // Comparaison (les cases arrivent par SSE) : progression réelle, moins cher de chaque ligne, colonne
  // gagnante, total qui clignote quand il change, montant du verdict qui défile.
  // ------------------------------------------------------------------------------------------------
  const suivreProgression = (comparaison) => {
    const cases = comparaison.querySelectorAll(".tableau-prix td.case");
    const barreProgression = comparaison.querySelector(".attente-resume .barre-chargement");
    const compte = comparaison.querySelector(".progression-compte");
    if (!cases.length || !barreProgression) return;
    const faites = [...cases].filter((td) => !td.querySelector(".attente")).length;
    if (faites > 0) {
      barreProgression.classList.add("determinee");
      barreProgression.style.setProperty("--progression", String(faites / cases.length));
    }
    if (compte) compte.textContent = faites ? `${faites} / ${cases.length} prix` : "";
  };

  const surligner = (comparaison) => {
    comparaison.querySelectorAll(".tableau-prix tbody tr").forEach((ligne) => {
      const cases = [...ligne.querySelectorAll("td.case")];
      const montants = cases.map((td) => {
        const prix = td.querySelector("[data-centimes]");
        return prix ? Number(prix.dataset.centimes) : null;
      });
      const connus = montants.filter((m) => m !== null);
      const minimum = connus.length >= 2 ? Math.min(...connus) : null;
      cases.forEach((td, i) => td.classList.toggle("moins-cher", minimum !== null && montants[i] === minimum));
    });
    const verdict = comparaison.querySelector("[data-gagnant]");
    const gagnant = verdict ? verdict.dataset.gagnant : null;
    comparaison.classList.toggle("gagnant-incomplet", Boolean(verdict?.querySelector(".verdict-gagnant.incomplet")));
    comparaison.querySelectorAll(".tableau-prix [data-magasin]").forEach((el) => {
      el.classList.toggle("gagnant", gagnant !== null && el.dataset.magasin === gagnant);
    });
  };

  // Le grand montant du verdict défile de 0 à sa valeur (une seule fois).
  const fairDefilerMontant = (el) => {
    if (el.dataset.anime) return;
    el.dataset.anime = "1";
    const fin = Number(el.dataset.centimes);
    const euros = el.querySelector(".etq");
    const centimes = el.querySelector(".etq-c");
    if (!Number.isFinite(fin) || fin <= 0 || moinsDeMouvement.matches || !euros || !centimes) return;
    const texteEuros = euros.firstChild;
    const texteCentimes = centimes.firstChild;
    if (!texteEuros || !texteCentimes) return;
    const duree = 750;
    const depart = performance.now();
    const etape = (maintenant) => {
      const avance = Math.min(1, (maintenant - depart) / duree);
      const valeur = Math.round(fin * (1 - Math.pow(1 - avance, 3)));
      texteEuros.nodeValue = String(Math.floor(valeur / 100));
      texteCentimes.nodeValue = `,${String(valeur % 100).padStart(2, "0")} €`;
      if (avance < 1) requestAnimationFrame(etape);
    };
    requestAnimationFrame(etape);
  };

  let enAttente = false;
  new MutationObserver((mutations) => {
    // Un total vient de changer : un bref éclat jaune attire l'œil.
    for (const m of mutations) {
      const td = m.target instanceof Element ? m.target.closest(".tableau-prix tfoot td") : null;
      if (td) {
        td.classList.remove("maj");
        void td.offsetWidth;
        td.classList.add("maj");
      }
    }
    if (enAttente || !document.querySelector(".comparaison")) return;
    enAttente = true;
    requestAnimationFrame(() => {
      enAttente = false;
      const comparaison = document.querySelector(".comparaison");
      if (!comparaison) return;
      suivreProgression(comparaison);
      surligner(comparaison);
      const montant = comparaison.querySelector(".verdict-prix[data-centimes]");
      if (montant) fairDefilerMontant(montant);
    });
  }).observe(document.body, { childList: true, subtree: true });
})();
