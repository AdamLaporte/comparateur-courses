// Comportements de l'interface, sans framework. Chargé (defer) sur toutes les pages ;
// chaque partie ne s'active que si ses éléments sont présents. Le site reste utilisable sans ce fichier.
(() => {
  "use strict";

  // --- Accueil : « Me localiser » remplit le lieu avec la position du navigateur, puis envoie. ---
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
      if (libelle) libelle.textContent = "Localisation…";
      navigator.geolocation.getCurrentPosition(
        (position) => {
          champ.value = `${position.coords.latitude.toFixed(5)},${position.coords.longitude.toFixed(5)}`;
          champ.form.submit();
        },
        () => {
          boutonLocaliser.disabled = false;
          if (libelle) libelle.textContent = texteInitial;
          signaler("Localisation refusée ou impossible : saisissez votre ville ou votre code postal.");
        },
        { timeout: 10000, maximumAge: 300000 },
      );
    });
  }

  // --- Magasins : carte (Leaflet) avec un repère numéroté par magasin, liée à la liste. ---
  const conteneurCarte = document.getElementById("carte-magasins");
  const donneesCarte = document.getElementById("donnees-carte");
  if (conteneurCarte && donneesCarte) {
    const dessinerCarte = () => {
      if (!window.L || conteneurCarte.dataset.prete) return; // Leaflet absent (hors ligne) : la liste suffit.
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
      for (const m of d.magasins) {
        const enseigne = String(m.enseigne).replace(/[^a-z]/g, "");
        const repere = L.marker([m.lat, m.lon], {
          icon: L.divIcon({ className: `repere ${enseigne}`, html: `<span>${Number(m.n)}</span>`, iconSize: [30, 30] }),
          title: `${m.n}. ${m.nom}`,
          alt: `${m.n}. ${m.nom}`,
        }).addTo(carte);
        reperes.set(String(m.n), repere);
        points.push([m.lat, m.lon]);
      }
      carte.fitBounds(points, { padding: [36, 36], maxZoom: 15 });

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

  // --- Ma liste : après un ajout, on vide la recherche pour enchaîner l'article suivant. ---
  document.body.addEventListener("htmx:afterRequest", (evenement) => {
    const element = evenement.detail.elt;
    if (!evenement.detail.successful || !element || !element.closest || !element.closest(".suggestion")) return;
    const recherche = document.getElementById("q");
    if (recherche) {
      recherche.value = "";
      recherche.focus();
    }
  });

  // --- Ma liste : glisser-déposer une photo de ticket sur la zone prévue (sinon le clic suffit). ---
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

  // --- Comparaison : met en avant le prix le plus bas de chaque ligne et la colonne gagnante. ---
  const surligner = () => {
    const comparaison = document.querySelector(".comparaison");
    if (!comparaison) return;
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
    comparaison.querySelectorAll(".tableau-prix [data-magasin]").forEach((el) => {
      el.classList.toggle("gagnant", gagnant !== null && el.dataset.magasin === gagnant);
    });
  };

  let enAttente = false;
  new MutationObserver(() => {
    if (enAttente || !document.querySelector(".comparaison")) return;
    enAttente = true;
    requestAnimationFrame(() => {
      enAttente = false;
      surligner();
    });
  }).observe(document.body, { childList: true, subtree: true });
})();
