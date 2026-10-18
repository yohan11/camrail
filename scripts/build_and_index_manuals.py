import os
import sys
import hashlib
from datetime import datetime
from pathlib import Path

# Add backend directory to path
backend_dir = Path("D:/camrail-main/backend").resolve()
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from camrail_pdf_base import CAMRAILManualPDF
from app.database import SessionLocal
from app.models.schemas import Document, DocumentPage, DocumentChunk, SecurityGroup, User
from app.services.indexing import index_document
from app.services.document_processor import process_document

STORAGE_DOCS_DIR = backend_dir / "storage" / "documents"
DOCS_EXPORT_DIR = Path("D:/camrail-main/Documentation RailMind Lite").resolve()
STORAGE_DOCS_DIR.mkdir(parents=True, exist_ok=True)
DOCS_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# ==============================================================================
# DOCUMENT 1: RDA-SEC-01 - Manuel Général de Sécurité et de Circulation Ferroviaire
# ==============================================================================
def create_doc_1(out_pdf_path: Path):
    pdf = CAMRAILManualPDF("REF: CAMRAIL-RDA-SEC-01 / V4.1", "Manuel Général de Sécurité et de Circulation Ferroviaire")
    
    # PAGE 1: Organisation & Principes Généraux
    pdf.add_page()
    pdf.render_page_header(1, "Préambule, Cadre Réglementaire et Organisation", "Réglementation de sécurité des circulations sur le réseau ferré camerounais")
    pdf.render_section("1.1. Objet et champ d'application")
    pdf.render_paragraph(
        "Le présent Règlement Général de Sécurité (RGS) s'applique sans exception à l'ensemble des circulations ferroviaires exploitées par la société CAMRAIL sur le réseau ferroviaire national du Cameroun. Ce réseau à voie unique et écartement métrique (1 000 mm) comprend l'axe Transcam I reliant Douala à Yaoundé (262 kilomètres de tracé accidenté à travers la forêt équatoriale et les reliefs escarpés de la vallée du Nyong) et l'axe Transcam II reliant Yaoundé à Ngaoundéré (652 kilomètres traversant le plateau central et les savanes de l'Adamaoua). Sont assujettis aux présentes prescriptions tous les trains de voyageurs express et omnibus, les trains de marchandises lourds, les convois d'hydrocarbures de la Société Camerounaise des Dépôts Pétroliers (SCDP), ainsi que les engins spéciaux de voie et draisines d'inspection."
    )
    pdf.render_section("1.2. Chaîne de commandement opérationnelle")
    pdf.render_paragraph(
        "L'organisation de la sécurité repose sur une structure hiérarchique stricte et centralisée. Au sommet se trouve le Directeur des Opérations Ferroviaires (DOF), assisté par le Chef du Département Sécurité et Circulation (DSC). La régulation en temps réel de tous les mouvements est assurée 24 heures sur 24 par le Poste Central de Régulation (PCR), installé au siège de Douala-Bassa. Aucun train ne peut être mis en marche, arrêté hors gare, ni dépasser un point de croisement sans ordre formel émanant du Régulateur de Ligne. Sur le terrain, l'autorité ferroviaire est déléguée aux Chefs de Gare dans leurs emprises respectives et aux Conducteurs de Ligne pour la conduite technique et la maîtrise de vitesse des rames."
    )
    pdf.render_callout(
        "RESPONSABILITÉ DU CONDUCTEUR",
        "Le conducteur est seul maître à bord de sa machine. En aucune circonstance, il ne doit obtempérer à un ordre verbal contradictoire qui enfreindrait une règle de signalisation fermée ou une limitation de vitesse de voie sans présentation d'un bulletin d'ordre écrit régulier."
    )

    # PAGE 2: Cantonnement Téléphonique & Intervalles
    pdf.add_page()
    pdf.render_page_header(2, "Régimes d'Exploitation et Cantonnement", "Espacement absolu des convois sur voie unique sans block automatique")
    pdf.render_section("2.1. Principe fondamental du cantonnement absolu")
    pdf.render_paragraph(
        "En raison de l'absence de block automatique lumineux intégral sur la majorité des sections du réseau, l'espacement des trains est assuré selon le régime du Cantonnement Téléphonique Manuel (CTM). Ce principe repose sur une règle absolue : un canton (portion de voie ferrée délimitée entre deux gares de croisement consécutives) ne peut être occupé que par un seul train à la fois, quel que soit le type de convoi. La vitesse maximale autorisée en voie libre sur rail 54 kg/m est fixée à 80 km/h pour les trains de voyageurs et à 60 km/h pour les trains de marchandises lourds."
    )
    pdf.render_section("2.2. Échange obligatoire de dépêches téléphoniques")
    pdf.render_paragraph(
        "Avant d'expédier un convoi, le chef de gare expéditeur doit obtenir l'accord formel du chef de gare destinataire par l'échange d'une formule codifiée transmise par le réseau téléphonique ferroviaire ou radio VHF sécurisée. La Demande de Voie Libre (DVL) est prononcée distinctement : 'Gare de Makak demande voie libre pour train numéro 172 partant à 14h20'. Le chef de gare destinataire vérifie l'absence totale de convoi engagé, inscrit l'heure au Registre Modèle R-8, et répond : 'Gare de Maloumé accorde voie libre pour train numéro 172, accord numéro 45'. Toute omission ou abréviation est considérée comme une infraction grave de classe A."
    )
    headers_c = ["Section de Ligne", "Type de Cantonnement", "Vitesse Max Voyageurs", "Vitesse Max Fret"]
    rows_c = [
        ["Douala - Edéa (PK 0 à 88)", "Block Manuel Assisté", "80 km/h", "60 km/h"],
        ["Edéa - Eseka (PK 88 à 174)", "Cantonnement Téléphonique", "70 km/h", "50 km/h"],
        ["Eseka - Maloumé (PK 174 à 245)", "Cantonnement Téléphonique Renforcé", "50 km/h", "40 km/h"],
        ["Yaoundé - Bélabo (PK 262 à 557)", "Cantonnement Téléphonique", "75 km/h", "55 km/h"],
    ]
    pdf.render_table(headers_c, rows_c, [50, 48, 38, 38])

    # PAGE 3: Signalisation de Voie & Franchissements
    pdf.add_page()
    pdf.render_page_header(3, "Système de Signalisation Optique", "Signaux d'entrée de gare, signaux de voie et tableaux indicateurs")
    pdf.render_section("3.1. Signaux d'entrée et disques d'avertissement")
    pdf.render_paragraph(
        "La signalisation optique protège les gares de croisement contre les prises en écharpe et collisions frontales. À l'approche de chaque gare, à une distance de 1 200 mètres, se trouve le Disque Rouge d'Avertissement (signal fixe mécanique ou lumineux). Lorsque le disque est présenté fermé, le conducteur doit immédiatement actionner son robinet de frein pour réduire sa vitesse à moins de 30 km/h, avec l'obligation stricte d'être en mesure de s'arrêter avant le carré d'entrée de gare. Le Carré Rouge Lumineux (deux feux rouges horizontaux ou un feu rouge fixe) matérialise l'Arrêt Absolu. Aucun essieu ne doit franchir ce jalon sans autorisation écrite."
    )
    pdf.render_section("3.2. Franchissement exceptionnel sous bulletin C-14")
    pdf.render_paragraph(
        "En cas d'avarie technique d'un signal d'entrée bloqué en position de fermeture par défaut, le conducteur a l'interdiction formelle de poursuivre sa marche de sa propre initiative. Le chef de gare doit se rendre physiquement au pied de la locomotive ou dépêcher l'aiguilleur pour remettre en main propre le Bulletin d'Autorisation de Franchissement C-14. Ce document papier numéroté précise la cause du dérangement, le numéro de l'appareil de voie défaillant et impose une vitesse d'approche prudente à vue ne dépassant en aucun cas 15 km/h jusqu'au franchissement complet des aiguilles d'entrée."
    )
    pdf.render_callout(
        "SIGNAL FERMÉ SANS BULLETIN",
        "Tout conducteur franchissant un carré rouge sans détention physique du Bulletin C-14 dûment complété est immédiatement relevé de ses fonctions de conduite et traduit devant la Commission Centrale de Discipline Ferroviaire."
    )

    # PAGE 4: Passages à Niveau & Prévention des Collisions
    pdf.add_page()
    pdf.render_page_header(4, "Sécurité aux Passages à Niveau", "Règles d'approche, franchissement et procédures en zone urbaine")
    pdf.render_section("4.1. Typologie des passages à niveau sur le réseau")
    pdf.render_paragraph(
        "Le réseau CAMRAIL compte plus de 180 passages à niveau (PN) classés en deux catégories principales selon l'intensité du trafic routier sécant. Les Passages à Niveau de Type A sont des passages gardés, munis de barrières levantes manuelles ou électriques, protégés par des agents gardes-barrières assermentés. Les Passages à Niveau de Type B sont des passages non gardés, équipés de panneaux de signalisation routière avancée, d'une croix de Saint-André rétroréfléchissante et d'un panneau Stop imposant l'arrêt absolu aux véhicules routiers. La zone périurbaine de Douala (PK 0 à PK 22) et les traversées d'Edéa et de Yaoundé concentrent plus de 70% des incidents avec les usagers de la route."
    )
    pdf.render_section("4.2. Prescription de signal sonore à l'approche")
    pdf.render_paragraph(
        "À l'approche de tout passage à niveau, qu'il soit gardé ou non, le conducteur de la locomotive doit actionner l'avertisseur sonore bi-ton (sifflet pneumatique) à l'aplomb du poteau indicateur 'S' situé à 200 mètres en amont. Le signal sonore doit être maintenu par impulsions successives d'au moins 3 secondes jusqu'au franchissement total du croisement routier par la locomotive de tête. De nuit ou par temps de brouillard dense en forêt, les projecteurs principaux de cabine doivent être commutés en mode grand faisceau dès le franchissement de la borne des 500 mètres."
    )
    pdf.render_paragraph(
        "En cas de signalement d'une barrière endommagée, de panne du mécanisme de fermeture ou d'absence signalée du garde-barrière, le PCR diffuse immédiatement un Ordre de Ralentissement de Voie (ORV) fixant la vitesse de franchissement du passage à niveau à 10 km/h au maximum, avec obligation d'arrêt préalable si des piétons ou véhicules sont engagés sur le gabarit."
    )

    # PAGE 5: Composition, Masse et Freinage Continu
    pdf.add_page()
    pdf.render_page_header(5, "Normes de Freinage et Composition des Trains", "Calcul du pourcentage de freinage et essais de continuité")
    pdf.render_section("5.1. Pression réglementaire de Conduite Générale (CG)")
    pdf.render_paragraph(
        "Toutes les rames circulant sur le réseau CAMRAIL doivent être équipées du freinage continu automatique à air comprimé (système Westinghouse ou Knorr-Bremse). La Conduite Générale (CG) traverse l'intégralité du train via des boyaux flexibles d'accouplement accouplés entre chaque véhicule. La pression d'air de régime normal de la Conduite Générale est strictement calibrée à 5,0 bars (avec une marge de tolérance opérationnelle comprise entre 4,9 et 5,1 bars). Une fuite supérieure à 0,3 bar en une minute sur une rame stationnaire interdit tout départ."
    )
    pdf.render_section("5.2. Essai de frein obligatoire avant départ")
    pdf.render_paragraph(
        "Aucun convoi ne peut quitter sa gare de formation sans la réalisation complète de l'essai de frein réglementaire. Cet essai comporte trois étapes incompressibles : l'essai de serrage complet commandé par le mécanicien au robinet de frein 26-L (dépression de 1,5 bar à la CG), le contrôle visuel de l'application des semelles de frein sur chaque essieu par les visitateurs de gare, et l'essai de continuité en queue. Pour ce dernier, le chef de train ouvre le robinet d'extrémité du dernier wagon : la chute de pression doit être instantanément constatée au manomètre de la cabine de conduite."
    )
    headers_f = ["Catégorie de Train", "Longueur Max (m)", "Charge Max (t)", "Pourcentage Frein Min"]
    rows_f = [
        ["Voyageurs Express (Intercity)", "420 m (14 voitures)", "750 t", "75 %"],
        ["Marchandises Standard", "650 m (30 wagons)", "1 600 t", "55 %"],
        ["Trains Lourds Hydrocarbures", "500 m (24 citernes)", "1 450 t", "60 %"],
        ["Trains de Grumes de Bois", "480 m (20 wagons plats)", "1 350 t", "50 %"],
    ]
    pdf.render_table(headers_f, rows_f, [52, 45, 38, 39])

    # PAGE 6: Procédures d'Urgence et Protection de Rame
    pdf.add_page()
    pdf.render_page_header(6, "Mesures d'Urgence et Détresse en Ligne", "Arrêt imprévu, protection par pétards et torches de détresse")
    pdf.render_section("6.1. Mesures immédiates lors d'un arrêt accidentel")
    pdf.render_paragraph(
        "Dès qu'un train se trouve immobilisé en pleine voie par suite d'une avarie de locomotive, d'un bris d'attelage, d'une chute de pression brutale à la conduite générale ou d'un obstacle sur la voie, le conducteur et le chef de train doivent immédiatement déclencher la procédure de protection d'urgence. Le conducteur bascule ses fanaux avant en feux rouges clignotants et émet sans délai sur le canal radio VHF d'urgence 156.800 MHz le message d'alerte : 'URGENCE ARRÊT - Train X en détresse au PK Y entre gare A et gare B - Voie obstruée'."
    )
    pdf.render_section("6.2. Pose réglementaire des pétards détonateurs")
    pdf.render_paragraph(
        "La protection arrière du train doit être assurée sans attendre par le chef de train ou le garde-frein, qui se porte à pied vers l'arrière du convoi. Il a l'obligation stricte de poser sur le champignon du rail trois pétards ferroviaires de détonation disposés de la manière suivante : le premier pétard à 800 mètres de l'arrière de la rame, le deuxième pétard à 900 mètres et le troisième pétard à 1 000 mètres. Les pétards sont fixés sur le rail extérieur dans les courbes. Si la visibilité est inférieure à 100 mètres en raison de pluies diluviennes ou de brouillard, une torche pyrotechnique rouge de détresse d'une durée de 20 minutes doit être allumée à 1 000 mètres."
    )
    pdf.render_callout(
        "DISPOSITIF D'ARRÊT D'URGENCE",
        "L'explosion d'un seul pétard sous la première roue d'une locomotive impose au conducteur l'arrêt d'urgence absolu immédiat par vidange intégrale de la conduite générale, sans chercher à identifier l'obstacle."
    )

    # PAGE 7: Saison des Pluies et Zones Géologiques Critiques
    pdf.add_page()
    pdf.render_page_header(7, "Exploitation en Période Géologique Critique", "Gestion des risques d'éboulement, glissements de terrain et crues")
    pdf.render_section("7.1. Secteurs à haute vulnérabilité géotechnique")
    pdf.render_paragraph(
        "Le tracé du Transcam traverse des zones montagneuses et forestières caractérisées par des sols ferrallitiques et latéritiques soumis à de fortes précipitations équatoriales (plus de 4 000 mm de pluie annuelle dans le bassin du Wouri et de la Sanaga). Deux secteurs sont classés en zone de vigilance rouge permanente : le tronçon PK 120 - PK 174 (falaises d'Edéa et défilés rocheux de la Sanaga) et le tronçon PK 174 - PK 245 (secteur d'Eseka, Maloumé et Makak). Dans ces zones, les talus de déblai peuvent subir des glissements de terrain massifs capables d'emporter la plateforme ferroviaire ou de recouvrir les voies sous plusieurs mètres de boue."
    )
    pdf.render_section("7.2. Dispositif de veille 'Alerte Pluie'")
    pdf.render_paragraph(
        "Dès que les relevés pluviométriques locaux dépassent 80 mm d'eau en moins de six heures, le Chef de District Voie ordonne l'activation de l'Alerte Pluie de niveau 2. Les trains de voyageurs voient leur vitesse automatiquement plafonnée à 40 km/h sur les zones répertoriées. Une draisine pilote d'éclaireur doit obligatoirement précéder le premier train commercial de chaque matin avec un intervalle de 20 minutes. Tout affouillement supérieur à 10 centimètres sous les traverses impose la fermeture immédiate de la ligne jusqu'à consolidation par enrochements."
    )

    # PAGE 8: Habilitations, Formation et Contrôle
    pdf.add_page()
    pdf.render_page_header(8, "Habilitations Professionnelles et Éthique", "Contrôles médicaux, audits en ligne et politique de sécurité")
    pdf.render_section("8.1. Validité des titres de sécurité du personnel roulant")
    pdf.render_paragraph(
        "L'exercice des fonctions de conducteur de train, d'aide-conducteur, de chef de sécurité de gare et d'aiguilleur est subordonné à la détention d'une Habilitation de Sécurité Ferroviaire (HSF) en cours de validité. Cette habilitation fait l'objet d'un examen médical d'aptitude psychotechnique et sensorielle semestriel, incluant un dépistage systématique des drogues et de l'alcoolémie. Le taux d'alcoolémie toléré est de 0,00 g/l de sang : tout contrôle positif entraîne la suspension conservatoire immédiate du titre de sécurité et la convocation devant le conseil de discipline sous 48 heures."
    )
    pdf.render_section("8.2. Audits inopinés et dépouillement des tachygraphes")
    pdf.render_paragraph(
        "Chaque locomotive en service est équipée d'un enregistreur tachymétrique numérique scellé (boîte noire modèle Deuta-Werke ou Hasler Teloc). Cet appareil enregistre en continu la vitesse réelle, la position du combinateur de marche, les pressions de freinage et les cycles de manipulation de la pédale de veille automatique VACMA. La cellule d'audit de la Direction Sécurité procède au dépouillement hebdomadaire aléatoire d'au moins 25% des bandes tachymétriques. Tout dépassement de vitesse limite supérieur à 5 km/h fait l'objet d'un rapport disciplinaire automatique."
    )
    pdf.render_callout(
        "RÉGLEMENTATION OFFICIELLE",
        "La sécurité des circulations est l'affaire de tous. Aucune considération commerciale ou d'horaire ne peut justifier la transgression délibérée d'une prescription de sécurité ferroviaire."
    )

    pdf.output(str(out_pdf_path))
    print(f"[OK] Généré : {out_pdf_path.name} (8 pages)")


# ==============================================================================
# DOCUMENT 2: RDA-MNT-02 - Guide Technique Maintenance Voies & Appareils
# ==============================================================================
def create_doc_2(out_pdf_path: Path):
    pdf = CAMRAILManualPDF("REF: CAMRAIL-RDA-MNT-02 / V3.4", "Guide Technique Maintenance Voies et Appareils de Voie")
    
    # PAGE 1: Superstructure de Voie
    pdf.add_page()
    pdf.render_page_header(1, "Superstructure et Composants de Voie", "Profils de rail, traverses et attaches sur voie métrique 1 000 mm")
    pdf.render_section("1.1. Profils de rails en exploitation")
    pdf.render_paragraph(
        "La superstructure de la voie ferrée du réseau CAMRAIL est constituée de rails en acier au manganèse laminé de profil Vignole à patin large. Sur le réseau, trois profils de rail coexistent en fonction des campagnes de renouvellement successives : le rail de 54 kg par mètre linéaire (profil 54 E1 / UIC 54) posé sur les tronçons modernes à fort trafic entre Douala et Edéa et sur les zones de renouvellement du Transcam II ; le rail de 36 kg/m (profil standard colonial français) encore présent sur d'importants segments du plateau central ; et le rail résiduel de 30 kg/m en cours d'éradication progressive sur les voies de service et triages."
    )
    pdf.render_section("1.2. Traverses et système de fixation")
    pdf.render_paragraph(
        "L'assise des rails repose sur deux types principaux de traverses : les traverses en bois dur tropical indigène, principalement taillées dans l'essence d'Azobé (Lophira alata) réputée pour sa densité exceptionnelle et sa résistance naturelle aux attaques fongiques et aux termites, imprégnées sous pression de créosote chaude ; et les traverses biblocs en béton armé type Vagneux ou Sonneville reliées par une entretoise métallique en profilé d'acier laminé. Les attaches sont constituées de crapauds élastiques Nabla (serrage au couple de 180 N·m) ou de clips Pandrol e-Clip offrant une excellente résistance au cheminement longitudinal des rails."
    )

    # PAGE 2: Tolérances Géométriques
    pdf.add_page()
    pdf.render_page_header(2, "Tolérances Géométriques et Normes de Pose", "Écartement, nivellement, dévers et alignement sur voie métrique")
    pdf.render_section("2.1. Écartement réglementaire de la voie")
    pdf.render_paragraph(
        "L'écartement nominal de la voie métrique CAMRAIL est fixé rigoureusement à 1 000 millimètres mesuré entre les faces actives des champignons de rail à 14 millimètres en dessous du plan de roulement. Les tolérances d'écartement sont définies selon trois seuils d'action technique : le seuil d'entretien normal autorise un écartement compris entre 997 mm (-3 mm) et 1 010 mm (+10 mm) en alignement droit. En courbe de rayon inférieur à 300 mètres, un surécartement constructif de 10 mm est appliqué pour faciliter l'inscription des bogies rigides des locomotives CC 2200."
    )
    pdf.render_section("2.2. Seuils critiques d'intervention")
    pdf.render_paragraph(
        "Le seuil d'intervention d'urgence (Niveau 3) est atteint dès que l'écartement mesuré dépasse 1 025 mm ou descend sous 992 mm. Si l'écartement atteint 1 035 mm, le risque d'ouverture de voie avec chute d'essieu entre les rails devient imminent : la voie doit être immédiatement neutralisée et interdite à toute circulation commerciale. Le nivellement transversal (différence de hauteur entre les deux files de rail) ne doit pas présenter de gauche supérieur à 4 millimètres par mètre sous charge."
    )
    headers_g = ["Paramètre Géométrique", "Valeur Nominale", "Tolérance Entretien", "Seuil Neutralisation"]
    rows_g = [
        ["Écartement en alignement", "1 000 mm", "-3 mm à +10 mm", "> 1 035 mm ou < 990 mm"],
        ["Écartement courbe R < 300m", "1 010 mm", "-2 mm à +15 mm", "> 1 040 mm"],
        ["Gauche de voie (sur 3m)", "0 mm", "< 6 mm", "> 12 mm"],
        ["Flèche d'alignement (corde 10m)", "0 mm", "< 5 mm", "> 15 mm"],
    ]
    pdf.render_table(headers_g, rows_g, [48, 42, 42, 42])

    # PAGE 3: Appareils de Voie et Aiguillages
    pdf.add_page()
    pdf.render_page_header(3, "Maintenance des Appareils de Voie", "Aiguillages, cœurs de croisement et tringles de manœuvre")
    pdf.render_section("3.1. Structure d'un branchement simple")
    pdf.render_paragraph(
        "Les appareils de voie assurent le changement d'itinéraire des trains entre voie principale et voies d'évitement ou de triage. Un branchement simple comporte trois sous-ensembles fondamentaux : le demi-ensemble d'aiguillage (composé de deux aiguilles mobiles en acier usiné et de deux rails contre-aiguilles fixes), la voie intermédiaire de raccordement, et le croisement comportant le cœur en acier moulé au manganèse et les deux contre-rails de guidage. Les modèles standardisés à CAMRAIL sont à tangente 0,09 (angle d'environ 5°08') et tangente 0,11 (angle de 6°17')."
    )
    pdf.render_section("3.2. Cotes de calage et usure des cœurs")
    pdf.render_paragraph(
        "La cote de protection de la pointe de cœur est fixée à 956 mm (tolérance ± 1 mm) : elle garantit que le boudin de roue ne heurtera jamais la pointe de cœur de face lors d'un mouvement talon-pointe. La cote d'ornière de contre-rail est de 41 mm (± 1 mm). Les aiguilleurs et brigadiers de voie doivent inspecter chaque semaine l'état des coussinets de glissement des aiguilles, éliminer toute trace de sable ou de gravillons de ballast et appliquer un lubrifiant graphité spécifique. Tout jeu résiduel supérieur à 2 mm entre la pointe d'aiguille fermée et le rail contre-aiguille interdit le passage des trains."
    )

    # PAGE 4: Ballast, Criblage et Assainissement
    pdf.add_page()
    pdf.render_page_header(4, "Ballast et Plateforme Ferroviaire", "Granulométrie, portance, assainissement et bourrage mécanique")
    pdf.render_section("4.1. Qualité et granulométrie du ballast")
    pdf.render_paragraph(
        "Le ballast joue un rôle mécanique fondamental dans la tenue de la voie ferrée : il transmet et répartit les charges d'essieu sur la plateforme de terrassement, offre une élasticité dynamique lors du passage des rames et permet l'évacuation rapide des eaux pluviales. Les spécifications techniques CAMRAIL imposent l'usage exclusif de concassé de roche magmatique dure (basalte des carrières du Mont Cameroun ou granite compact), exempt de particules altérées. La granulométrie normalisée est de 25/50 mm, avec un pourcentage d'éléments fins inférieur à 1%."
    )
    pdf.render_section("4.2. Épaisseur et pollution latéritique")
    pdf.render_paragraph(
        "L'épaisseur de ballast propre sous la sous-face des traverses doit être au minimum de 20 centimètres sur traverses bois et de 25 centimètres sur traverses béton. La banquette latérale doit déborder d'au moins 40 centimètres au-delà de la tête de traverse avec un talus à 45°. Durant la saison des pluies équatoriale, les infiltrations d'eau provoquent des remontées de boue latéritique par pompage des traverses sous le passage des convois lourds. Ce phénomène de 'voie souillée' détruit la portance et impose un dégarnissage complet suivi d'un régalage de ballast neuf et d'un bourrage mécanique."
    )

    # PAGE 5: Dilatation Thermique et Longs Rails Soudés
    pdf.add_page()
    pdf.render_page_header(5, "Comportement Thermique des Longs Rails Soudés", "Contraintes thermiques, température neutre et prévention du flambement")
    pdf.render_section("5.1. Phénomène de dilatation en climat équatorial")
    pdf.render_paragraph(
        "Sur les sections modernisées en Longs Rails Soudés (LRS) où les joints éclissés ont été supprimés par soudure aluminothermique sur des longueurs de plusieurs kilomètres, les variations thermiques ne peuvent plus être absorbées par le jeu des éclisses. Au Cameroun, la température interne du rail peut atteindre 65°C en plein soleil sur les tronçons découverts de la savane du Nord, alors qu'elle descend à 18°C lors des nuits humides de saison fraîche. Cette amplitude thermique de près de 50°C génère des efforts longitudinaux colossaux atteignant plus de 80 tonnes de compression par file de rail."
    )
    pdf.render_section("5.2. Température de libération des contraintes")
    pdf.render_paragraph(
        "Pour équilibrer les contraintes de compression et de traction, la température neutre de fixation de la voie (température d'équilibrage des contraintes internes nulles) est fixée conventionnellement à 35°C (tolérance ± 3°C). Toute opération de soudure de LRS doit être réalisée soit à cette température naturelle, soit en appliquant des vérins tendeurs hydrauliques de libération des contraintes. Si les rails sont fixés à froid sans tension préalable, l'élévation thermique diurne provoquera immanquablement le flambement latéral de la voie, causant un déraillement majeur."
    )

    # PAGE 6: Ouvrages d'Art et Ponts Métalliques
    pdf.add_page()
    pdf.render_page_header(6, "Surveillance des Ouvrages d'Art", "Ponts métalliques, viaducs, culées et appareils d'appui")
    pdf.render_section("6.1. Patrimoine des ponts ferroviaires")
    pdf.render_paragraph(
        "Le réseau ferroviaire CAMRAIL comporte plus de 320 ponts, viaducs et dalots en béton armé ou en charpente métallique rivetée. Parmi les ouvrages stratégiques figurent les grands ponts métalliques à tablier supérieur franchissant les fleuves Sanaga à Edéa (pont de 240 mètres en poutres treillis Warren), Wouri, Nyong et Mbam. Les inspections périodiques de ces ouvrages sont programmées selon un rythme semestriel par les brigades spécialisées du Département Ouvrages d'Art (DOA) de la Direction des Installations Fixes."
    )
    pdf.render_section("6.2. Contrôle de la corrosion et affouillements")
    pdf.render_paragraph(
        "En milieu tropical humide et marin (proximité côtière de Douala), la corrosion atmosphérique des membrures métalliques constitue la première cause de vieillissement des ponts. Les assemblages rivetés et goussets d'extrémité doivent faire l'objet d'un piquage de rouille, d'un dégraissage et de l'application d'un complexe de peinture époxy-polyuréthane résistant aux embruns salins. Sous les appuis, les crues fluviales violentes provoquent l'affouillement du lit rocheux autour des piles en rivière : toute dépression supérieure à 50 cm impose la pose immédiate d'enrochements de protection en blocs de granit de 500 à 1 500 kg."
    )

    # PAGE 7: Auscultation et Contrôle Non Destructif
    pdf.add_page()
    pdf.render_page_header(7, "Détection des Défauts Internes du Rail", "Auscultation ultrasonore, ressuage et réparations d'urgence")
    pdf.render_section("7.1. Chariot d'auscultation ultrasonique")
    pdf.render_paragraph(
        "L'auscultation périodique des rails vise à détecter les défauts internes invisibles à l'œil nu avant qu'ils ne dégénèrent en rupture brutale sous essieu. CAMRAIL utilise des appareils d'auscultation ultrasonore portatifs et un chariot pousseur équipé de sondes émettrices-réceptrices piézoélectriques à ondes de cisaillement et de compression. Les sondes à 0° inspectent l'âme et la base du rail, les sondes à 45° et 70° scannent le champignon à la recherche de fissures transversales de fatigue (taches ovales) et de criques de patinage."
    )
    pdf.render_section("7.2. Classification et traitement des avaries de rail")
    pdf.render_paragraph(
        "Un défaut détecté est classé selon le barème de dangerosité : défaut de type A (fissure horizontale de moins de 15 mm, surveillance mensuelle) ; défaut de type B (fissure transversale de plus de 25% de la section du champignon, pose d'éclisses provisoires serrées à 4 boulons et limitation de vitesse à 30 km/h) ; et défaut de type C (fissure débouchante ou amorce de rupture totale, arrêt immédiat des circulations et remplacement d'urgence du coupon de rail d'une longueur minimale de 6 mètres sous 24 heures)."
    )

    # PAGE 8: Sécurité des Chantiers de Voie
    pdf.add_page()
    pdf.render_page_header(8, "Sécurité des Équipes de Travaux de Voie", "Interruption de circulation, jalonnement rouge et veilleur de sécurité")
    pdf.render_section("8.1. Régime d'interruption temporaire de circulation")
    pdf.render_paragraph(
        "Tous les travaux de maintenance lourde de voie (renouvellement de traverses, dégarnissage de ballast, soudures aluminothermiques) doivent obligatoirement s'effectuer sous le régime formel d'Interruption Temporaire de Circulation (ITC). Le chef de district doit obtenir auprès du PCR la confirmation écrite de l'engagement de l'intervalle de travaux via le bulletin modèle V-2. Ce document spécifie avec exactitude l'heure de début, l'heure de restitution impérative de la voie et les points kilométriques de début et fin de chantier."
    )
    pdf.render_section("8.2. Dispositif physique de protection de chantier")
    pdf.render_paragraph(
        "Sur le terrain, la zone de travail doit être protégée à ses deux extrémités par la pose d'un jalon d'arrêt temporaire (drapeau rouge fixe le jour, lanterne rouge la nuit) positionné à 500 mètres de la zone de travail, précédé de trois pétards détonateurs fixés à 800 mètres. Un veilleur de sécurité équipé d'une trompe sonore d'alarme à air comprimé doit se tenir en permanence en surveillance avancée. Dès l'audition de la trompe d'alarme, les ouvriers disposent de 30 secondes pour évacuer les voies et déposer tout outillage hors du gabarit cinématique."
    )

    pdf.output(str(out_pdf_path))
    print(f"[OK] Généré : {out_pdf_path.name} (8 pages)")


# ==============================================================================
# DOCUMENT 3: RDA-TRC-03 - Règlement Général Conduite & Matériel Traction
# ==============================================================================
def create_doc_3(out_pdf_path: Path):
    pdf = CAMRAILManualPDF("REF: CAMRAIL-RDA-TRC-03 / V2.8", "Règlement Général de Conduite et Matériel de Traction")
    
    # PAGE 1: Parc de Traction
    pdf.add_page()
    pdf.render_page_header(1, "Parc Moteur et Caractéristiques Électromécaniques", "Locomotives diesel-électriques de ligne et de manœuvre")
    pdf.render_section("1.1. Séries de locomotives de ligne en exploitation")
    pdf.render_paragraph(
        "Le parc de traction de ligne de CAMRAIL est composé principalement de trois grandes séries de locomotives diesel-électriques à six essieux moteurs réparties sur deux bogies Co-Co, adaptées aux fortes déclivités et aux conditions tropicales sévères. La série CC 2200 (constructeur General Electric / Alsthom, moteurs V12 turbocompressés développant 2 400 chevaux) assure traditionnellement la traction des trains de voyageurs Intercity et omnibus. La série CC 2600 (constructeur Bombardier Transportation, motorisation GM EMD 16-645 de 2 600 chevaux) est spécialisée dans les trains lourds de fret. La série moderne CC 3300 (constructeur Grindrod / NRE, motorisation EMD 710 de 3 300 chevaux) constitue le fer de lance de la traction des pondéreux et convois pétroliers sur le Transcam II."
    )
    pdf.render_section("1.2. Chaîne cinématique et transmission")
    pdf.render_paragraph(
        "La chaîne de traction repose sur un moteur thermique diesel 4 temps ou 2 temps suralimenté par turbocompresseur entraînant un alternateur principal triphasé à rotor sans bague. Le courant alternatif généré est redressé par un pont de diodes silicium haute puissance pour alimenter en courant continu les six moteurs de traction à excitation série suspendus par le nez aux essieux. La puissance aux jantes atteint 2 200 kW sur la série CC 3300, permettant un effort de traction au démarrage supérieur à 420 kN sur rail sec sablé."
    )

    # PAGE 2: Visite Pré-Départ
    pdf.add_page()
    pdf.render_page_header(2, "Visite de Prise en Charge au Dépôt", "Contrôles visuels, niveaux des fluides et organes mécaniques bas")
    pdf.render_section("2.1. Vérifications systématiques avant mise en route")
    pdf.render_paragraph(
        "Lors de la prise de service au dépôt principal de Douala-Bassa ou de Yaoundé-Mvolyé, l'équipe de conduite (conducteur titulaire et aide-conducteur) doit consacrer au minimum 30 minutes à la visite technique de prise en charge avant de sortir la locomotive de son garage. Les vérifications portent en premier lieu sur les niveaux de tous les fluides techniques : niveau d'huile du carter moteur à la jauge graduée (compléter avec de l'huile moteur 15W40 homologuée si nécessaire), niveau du liquide de refroidissement dans le vase d'expansion haute pression, et niveau d'huile des carters d'engrenages de traction."
    )
    pdf.render_section("2.2. Organes de roulement et sablières")
    pdf.render_paragraph(
        "Le tour de machine extérieur comprend l'inspection détaillée des organes de roulement et de choc. L'épaisseur des boudins de roue doit être mesurée au calibre à coulisse : elle ne doit en aucun cas être inférieure à 25 mm (cote nominale 32 mm), sous peine de risque de déraillement par franchissement d'aiguille. Les semelles de frein en matériau composite ou en fonte doivent présenter une épaisseur résiduelle minimale de 20 mm. Enfin, les quatre bacs à sable doivent être entièrement remplis de sable siliceux extra-sec tamisé à 1 mm pour assurer l'efficacité des injecteurs pneumatiques de sablage en cas de patinage."
    )

    # PAGE 3: Technique de Conduite et Profils Sévères
    pdf.add_page()
    pdf.render_page_header(3, "Techniques de Conduite et Maîtrise de Vitesse", "Négociation des rampes, combinateur de marche et patinage")
    pdf.render_section("3.1. Manipulation du combinateur de traction")
    pdf.render_paragraph(
        "Le combinateur de marche comporte 8 crans de traction crantés. Le passage d'un cran au suivant doit être exécuté de façon souple et progressive, en observant attentivement l'ampèremètre de courant de traction pour ne pas dépasser la zone rouge de surintensité thermique (fixée à 1 100 ampères par moteur de traction). Lors du démarrage en rampe avec un convoi lourd de marchandises, le conducteur doit afficher le cran 1, desserrer le frein direct de la machine dès la montée en pression du courant, puis monter progressivement les crans tout en actionnant le sablage intermittent pour prévenir tout amorçage de patinage."
    )
    pdf.render_section("3.2. Passage de la rampe sévère d'Eseka - Maloumé")
    pdf.render_paragraph(
        "Le profil en long du Transcam I présente entre Eseka et Maloumé une rampe continue de 25 millimètres par mètre sur plus de 18 kilomètres, combinée à des courbes de rayon serré de 250 mètres. Pour tout train de marchandises dépassant 1 100 tonnes remorquées, l'adjonction d'une locomotive d'allège en pousse en queue de convoi est strictement obligatoire au départ d'Eseka. Les conducteurs des deux locomotives doivent synchroniser leurs efforts par liaison radio VHF continue, le conducteur de tête dictant chaque changement de cran de traction."
    )

    # PAGE 4: Dispositif de Veille Automatique VACMA
    pdf.add_page()
    pdf.render_page_header(4, "Veille Automatique de Cabine VACMA", "Sécurité de l'agent seul en cabine et cycle chronométrique d'alerte")
    pdf.render_section("4.1. Principe de surveillance de vigilance")
    pdf.render_paragraph(
        "Toutes les locomotives de ligne sont équipées du système de Veille Automatique avec Contrôle de Maintien d'Appui (VACMA). Ce dispositif électromécanique et informatique surveille en permanence la vigilance physique du conducteur en exigeant de sa part des actions physiques régulières sur la pédale de plancher ou sur le bouton-poussoir situé sur l'accoudoir de cabine. Le principe impose une alternance entre périodes d'appui maintenu et relâchements brefs pour prouver la pleine conscience de l'agent de conduite."
    )
    pdf.render_section("4.2. Cycle temporel et freinage d'urgence")
    pdf.render_paragraph(
        "Le cycle chronométrique de la VACMA est strictement cadencé : le conducteur peut maintenir la pédale enfoncée pendant une durée maximale de 50 secondes consécutives. Dès la 50e seconde sans relâchement, un voyant lumineux orange s'allume au tableau de bord accompagné d'un avertisseur sonore strident (buzzer). Le conducteur dispose alors d'un délai impératif de 5 secondes pour relâcher puis réenfoncer la pédale. S'il n'exécute pas ce geste dans les 5 secondes imparties, la VACMA déclenche automatiquement et de manière irréversible le freinage d'urgence par vidange directe de la Conduite Générale et coupe l'alimentation électrique des moteurs de traction."
    )

    # PAGE 5: Freinage Pneumatique 26-L et Frein Rhéostatique
    pdf.add_page()
    pdf.render_page_header(5, "Gestion des Systèmes de Freinage", "Frein continu automatique 26-L, frein direct et frein rhéostatique")
    pdf.render_section("5.1. Rôles respectifs des organes de freinage")
    pdf.render_paragraph(
        "La cabine de conduite comprend deux robinets de frein principaux distincts : le Robinet de Frein Automatique 26-L qui commande l'ensemble des freins de la rame par variation de pression dans la Conduite Générale (CG), et le Robinet de Frein Indépendant (frein direct) qui agit exclusivement sur les cylindres de frein de la locomotive motrice. En ligne, les décélérations et arrêts doivent être exécutés exclusivement à l'aide du frein automatique 26-L pour assurer un freinage homogène sur tous les wagons et éviter les chocs violents de tamponnement."
    )
    pdf.render_section("5.2. Utilisation conjointe du frein rhéostatique dynamique")
    pdf.render_paragraph(
        "Dans les longues déclivités descendantes (notamment entre Maloumé et Edéa où la pente atteint 22 mm/m), le conducteur doit utiliser en priorité le frein rhéostatique dynamique. En inversant les connexions des moteurs de traction, ceux-ci fonctionnent comme des génératrices électriques débitant sur des bancs de résistances ventilées par de puissants extracteurs de toiture. Ce freinage électrique sans frottement permet de maintenir une vitesse stable sans user prématurément les semelles de frein mécaniques ni risquer la surchauffe thermique et l'éclatement des bandages de roues."
    )

    # PAGE 6: Diagnostic et Avaries en Pleine Voie
    pdf.add_page()
    pdf.render_page_header(6, "Diagnostic des Avaries et Pannes en Ligne", "Disjonction générale, isolement de bogie et perte de pression")
    pdf.render_section("6.1. Procédure lors d'une disjonction principale")
    pdf.render_paragraph(
        "Lorsqu'un déclenchement du disjoncteur principal survient en ligne, le conducteur doit immédiatement ramener le combinateur de marche au cran 0 (ralenti moteur) et identifier l'origine du défaut sur le tableau d'alarme lumineux. Trois anomalies majeures provoquent une disjonction : le défaut de masse électrique (isolation de l'alternateur ou d'un moteur de traction dégradée par l'humidité équatoriale), la température d'eau moteur supérieure à 98°C, ou la baisse de pression d'huile moteur sous 1,2 bar. Si le défaut de masse persiste, le conducteur actionne le commutateur d'isolement de bogie pour neutraliser les trois moteurs du bogie défectueux et repartir sur un seul bogie avec charge réduite."
    )
    pdf.render_section("6.2. Fuite d'air à la conduite générale")
    pdf.render_paragraph(
        "Une fuite importante ou une rupture de boyau de frein se manifeste par une chute rapide de pression à la CG visible au manomètre double aiguille. Le conducteur doit immédiatement immobiliser son train, appliquer le frein direct de la machine, serrer le frein à main mécanique de la locomotive et dépêcher l'aide-conducteur le long de la rame pour localiser le boyau éclaté ou le robinet d'arrêt fermé intempestivement. Tout boyau défectueux doit être remplacé par un boyau de rechange obligatoire logé dans le coffre d'outillage de cabine."
    )

    # PAGE 7: Organes de Choc et d'Attelage
    pdf.add_page()
    pdf.render_page_header(7, "Attelages, Organes de Choc et Sécurité Mécanique", "Attelages automatiques Willison, vis conventionnelle et gabarit")
    pdf.render_section("7.1. Typologie des systèmes d'attelage")
    pdf.render_paragraph(
        "Le matériel roulant CAMRAIL utilise deux technologies d'attelage : l'Attelage Automatique Central de type Willison (ou Alliance) monté sur les locomotives lourdes et les wagons de fret minéraliers et pétroliers récents, capable d'encaisser des efforts de traction supérieurs à 1 000 kN ; et l'attelage conventionnel à tendeur à vis et deux tampons latéraux équipant encore certaines voitures voyageurs omnibus et anciens wagons plats. Le panachage de ces deux technologies est rendu possible grâce à l'utilisation de coupleurs mixtes et maillons de transition forgés en acier spécial."
    )
    pdf.render_section("7.2. Vérification de l'enclenchement sécurisé")
    pdf.render_paragraph(
        "Lors de l'accrochage de wagons par attelage automatique Willison, la vitesse d'impact ne doit pas excéder 5 km/h. L'agent de manœuvre doit vérifier visuellement la retombée complète de la clavette verticale de verrouillage dans sa gorge. L'absence de retombée complète de la clavette crée un risque majeur de rupture d'attelage en ligne sous l'effet des secousses de traction dans les rampes. Les manchons d'accouplement de frein pneumatique doivent être verrouillés par demi-tour et suspendus à leur chaîne de repos pour éviter qu'ils ne traînent sur les traverses."
    )

    # PAGE 8: Éco-Conduite et Rapport de Marche
    pdf.add_page()
    pdf.render_page_header(8, "Éco-Conduite, Restitution et Rapport de Fin de Service", "Bilan gasoil, relevé des tachygraphes et garage en dépôt")
    pdf.render_section("8.1. Principes d'éco-conduite ferroviaire")
    pdf.render_paragraph(
        "Face aux coûts énergétiques et dans le respect des engagements environnementaux de CAMRAIL, les conducteurs doivent appliquer les règles d'éco-conduite enseignées au Centre de Formation Ferroviaire de Bassa (CFFB). La règle principale consiste à exploiter au maximum l'énergie cinétique accumulée en coupant la traction bien avant les zones de ralentissement ou les entrées de gare (conduite sur l'erre). Sur les tronçons descendants en faux-plat, la traction doit être ramenée à zéro, permettant une économie de plus de 15% de gasoil par rapport à une conduite saccadée."
    )
    pdf.render_section("8.2. Clôture de service et rapport technique")
    pdf.render_paragraph(
        "À l'arrivée au dépôt de destination, le conducteur procède aux opérations de remise de machine : maintien du moteur au ralenti pendant 5 minutes pour permettre le refroidissement équilibré des paliers de turbocompresseur, serrage à fond du frein à main mécanique, purge des réservoirs d'air auxiliaires pour éliminer les condensats d'eau, et calage des roues motrices par sabots d'arrêt en bois dur. Il remplit avec précision le Bulletin de Marche et consigne sur le Carnet de Bord de la Locomotive (CBL) toutes les anomalies observées au cours du trajet pour prise en charge par l'équipe de visite nocturne."
    )

    pdf.output(str(out_pdf_path))
    print(f"[OK] Généré : {out_pdf_path.name} (8 pages)")


# ==============================================================================
# DOCUMENT 4: RDA-URG-04 - Plan d'Intervention d'Urgence et Secours Ferroviaires
# ==============================================================================
def create_doc_4(out_pdf_path: Path):
    pdf = CAMRAILManualPDF("REF: CAMRAIL-RDA-URG-04 / V3.0", "Plan d'Intervention d'Urgence et de Secours Ferroviaires")
    
    # PAGE 1: Typologie et Niveaux d'Urgence
    pdf.add_page()
    pdf.render_page_header(1, "Classification et Niveaux d'Urgence Ferroviaire", "Cadre opérationnel du Plan d'Intervention d'Urgence (PIU)")
    pdf.render_section("1.1. Finalité du Plan d'Intervention d'Urgence")
    pdf.render_paragraph(
        "Le Plan d'Intervention d'Urgence (PIU) définit les dispositions opérationnelles, les responsabilités hiérarchiques et la coordination logistique nécessaires pour faire face à tout accident ou incident grave survenant sur le réseau ferroviaire exploité par CAMRAIL. Il a pour priorité absolue la sauvegarde de la vie humaine (passagers, personnel de bord et riverains), la prise en charge médicale d'urgence, la protection de l'environnement contre les déversements de matières toxiques, et le rétablissement ordonné des circulations ferroviaires dans les meilleurs délais de sécurité."
    )
    pdf.render_section("1.2. Gradation en trois niveaux d'urgence")
    pdf.render_paragraph(
        "Les événements accidentels sont classés en trois niveaux selon leur gravité intrinsèque : Niveau 1 (Incident Technique Simple) : avarie de locomotive sans déraillement, heurt de bétail sans blessé, retard important sans détresse humaine ; Niveau 2 (Accident Matériel Majeur) : déraillement d'un ou plusieurs wagons de fret, rupture de voie ou affouillement important sans victime corporelle ; Niveau 3 (Catastrophe Ferroviaire Majeure) : déraillement d'un train de voyageurs avec blessés ou victimes, collision entre trains, ou brèche sur un wagon-citerne d'hydrocarbures avec risque d'explosion ou d'incendie généralisé."
    )

    # PAGE 2: Alerte Initiale et Chaîne de Commandement
    pdf.add_page()
    pdf.render_page_header(2, "Transmission de l'Alerte et Cellule de Crise", "Message d'Alerte Initial (MAI) et activation du commandement")
    pdf.render_section("2.1. Déclenchement impératif dans les 3 minutes")
    pdf.render_paragraph(
        "En cas d'accident grave de niveau 2 ou 3, le conducteur ou le chef de train a l'obligation formelle d'émettre le Message d'Alerte Initial (MAI) dans un délai de trois minutes suivant l'arrêt complet de la rame. L'alerte est transmise en priorité par la radio VHF de bord sur le canal d'urgence 1 ou par téléphone satellitaire de cabine vers le Poste Central de Régulation (PCR) à Douala. En cas d'inopérance des moyens radio en zone forestière encaissée, le chef de train dépêche l'aide-conducteur vers la gare la plus proche avec un avis écrit de détresse."
    )
    pdf.render_section("2.2. Composition de la Cellule de Crise")
    pdf.render_paragraph(
        "Dès réception du MAI de niveau 3, le Régulateur Général déclenche immédiatement la sirène d'alerte du siège et convoque la Cellule de Crise au Centre de Commandement Opérationnel de Douala-Bassa. La cellule est présidée par le Directeur Général de CAMRAIL et regroupe le Directeur des Opérations, le Directeur des Installations Fixes, le Directeur du Matériel Roulant, le Directeur de la Sécurité QHSE, le Directeur de la Communication et le Médecin-Chef de l'Entreprise. La cellule est en liaison permanente avec les autorités administratives (Gouverneurs de Région, Préfets) et les services de secours de l'État."
    )

    # PAGE 3: Sécurisation du Périmètre et Rôles de Bord
    pdf.add_page()
    pdf.render_page_header(3, "Mesures Conservatoires de l'Équipage de Bord", "Protection bilatérale, coupure de l'énergie et confinement")
    pdf.render_section("3.1. Répartition des missions d'urgence à bord")
    pdf.render_paragraph(
        "Dès l'immobilisation consécutive à un accident, l'équipage de bord applique la stricte division des tâches d'urgence : le conducteur reste en cabine pour couper le moteur thermique, couper les disjoncteurs de batterie 72V, fermer le robinet d'arrêt de carburant d'urgence extérieur et assurer la protection avant de la voie sur 1 000 mètres à l'aide de pétards. Le chef de train prend la tête des opérations dans les voitures voyageurs, assisté des contrôleurs et agents de sécurité embarqués, tandis que le garde-frein assure la protection arrière réglementaire à 1 000 mètres."
    )
    pdf.render_section("3.2. Préservation formelle des traces et indices")
    pdf.render_paragraph(
        "Sauf motif impérieux de sauvetage de vies humaines en danger immédiat (incendie actif), il est rigoureusement interdit de déplacer des débris, de manœuvrer des robinets de frein ou de modifier la position des organes de commande de la locomotive avant l'arrivée de la Commission d'Enquête Technique. Les bandes tachymétriques de la locomotive et les registres de bord doivent être placés sous scellés immédiats par le chef de train sous le contrôle des officiers de police judiciaire compétents."
    )

    # PAGE 4: Secours Sanitaires et Triage Médical
    pdf.add_page()
    pdf.render_page_header(4, "Organisation des Secours Médicaux et Triage", "Poste Médical Avancé (PMA), évacuation et protocoles sanitaires")
    pdf.render_section("4.1. Établissement du Poste Médical Avancé (PMA)")
    pdf.render_paragraph(
        "En présence de blessés sur un train de voyageurs, le chef de train et le personnel formé aux premiers secours aménagent immédiatement un Poste Médical Avancé (PMA) sur un site plat, stable et sécurisé à au moins 50 mètres de la voie ferrée, en amont du vent pour éviter toute exposition aux fumées toxiques éventuelles. Le matériel médical d'urgence (trousses de secours de bord, brancards rigides, défibrillateurs semi-automatiques) est déployé pour prodiguer les premiers soins de réanimation et de pose de garrots compressifs."
    )
    pdf.render_section("4.2. Évacuation et triage des victimes")
    pdf.render_paragraph(
        "Dès l'arrivée des équipes du Corps National des Sapeurs-Pompiers et du SAMU, le médecin régulateur prend la direction des opérations médicales et classe les victimes selon le code de triage international : Urgence Absolue UA (bracelets rouges, pronostic vital engagé, évacuation prioritaire par hélicoptère ou ambulance médicalisée) ; Urgence Relative UR (bracelets jaunes, fractures et traumatismes sans détresse vitale) ; et Impliqués (bracelets verts, choc psychologique). Les blessés graves sont évacués vers les hôpitaux de référence conventionnés : Hôpital Général et Laquintinie à Douala, Hôpital Central et Cury à Yaoundé."
    )

    # PAGE 5: Risque Matières Dangereuses (MD)
    pdf.add_page()
    pdf.render_page_header(5, "Accidents de Wagons-Citernes d'Hydrocarbures", "Marchandises Dangereuses (MD), périmètre d'exclusion et dépollution")
    pdf.render_section("5.1. Risques spécifiques liés aux hydrocarbures")
    pdf.render_paragraph(
        "Le transport ferroviaire d'hydrocarbures liquides (essence super, gasoil, pétrole lampant et carburant aviation Jet A-1) pour le compte de la SCDP représente des volumes massifs pouvant atteindre 1,5 million de litres par convoi. En cas de déraillement avec brèche ou fuite sur une citerne, le risque majeur est l'incendie instantané par étincelle mécanique ou l'explosion de vapeur de liquide en ébullition (phénomène BLEVE). Tout wagon transportant des matières dangereuses est identifié par des plaques orange rectangulaires affichant le Code Danger et le Numéro ONU (ex: 33 / 1203 pour le supercarburant)."
    )
    pdf.render_section("5.2. Périmètre d'exclusion de 500 mètres")
    pdf.render_paragraph(
        "Dès le constat d'une fuite de liquide inflammable, le chef de train ordonne l'évacuation de tout le personnel et des populations riveraines dans un rayon d'au moins 500 mètres. L'usage de téléphones portables non antidéflagrants, de torches ordinaires ou de moteurs thermiques est strictement interdit dans la zone d'exclusion. Les équipes de secours de CAMRAIL déploient immédiatement des barrages flottants absorbants en polypropylène sur les cours d'eau en aval pour stopper la contamination des nappes phréatiques et des fleuves."
    )

    # PAGE 6: Trains de Secours et Équipes de Relevage
    pdf.add_page()
    pdf.render_page_header(6, "Mobilisation du Train de Secours et Relevage", "Grues ferroviaires, vérins hydrauliques et matériel lourd")
    pdf.render_section("6.1. Composition des rames de relevage d'urgence")
    pdf.render_paragraph(
        "CAMRAIL dispose de deux Trains de Secours et de Relevage (TSR) basés en alerte permanente dans les dépôts de Douala-Bassa et de Bélabo. Un TSR comprend une locomotive de traction dédiée, un wagon-atelier outillé équipé d'un groupe électrogène de 100 kVA, de compresseurs d'air, de postes de découpe oxyacétylénique et d'éclairages sur mâts télescopiques, un wagon porte-agrès avec vérins hydrauliques Luk et câbles en acier haute résistance, et un wagon dortoir pour l'équipe technique de 25 spécialistes de relevage."
    )
    pdf.render_section("6.2. Techniques d'enraillage et grue 80 tonnes")
    pdf.render_paragraph(
        "Pour le relevage des locomotives de ligne pesant plus de 115 tonnes, la grue ferroviaire automotrice Gottwald de 80 tonnes est acheminée sur site. Pour les wagons de marchandises déraillés sur la plateforme, l'enraillage s'effectue au moyen de ponts de vérinage hydrauliques et de sabots d'enraillage métalliques biseautés fixés sur les rails : les vérins soulèvent l'essieu tandis qu'un vérin horizontal ripe le bogie pour faire glisser les boudins de roue directement sur le rail en un seul mouvement contrôlé."
    )

    # PAGE 7: Enquête Technique et Boîtes Noires
    pdf.add_page()
    pdf.render_page_header(7, "Investigation Technique et Enquête d'Accident", "Lecture des bandes tachymétriques, métallurgie et topographie")
    pdf.render_section("7.1. Collecte méthodique des éléments matériels")
    pdf.render_paragraph(
        "Dès la sécurisation du site achevée, la Commission d'Enquête Technique Interne (CETI) procède au recueil rigoureux des données matérielles. Les enquêteurs réalisent un relevé topographique millimétrique du tracé sur 300 mètres en amont du point d'impact : mesure de l'écartement des rails tous les 3 mètres, contrôle des dévers et recherche des traces d'escalade du boudin sur le champignon du rail extérieur. L'état d'usure des semelles de frein, le jeu des traverses et la présence de corps étrangers sur la voie sont consignés par photographies géoréférencées."
    )
    pdf.render_section("7.2. Dépouillement des enregistreurs d'événements")
    pdf.render_paragraph(
        "L'enregistreur d'événements scellé de la locomotive est extrait en présence d'un huissier de justice et transféré au laboratoire d'analyse de Douala. Les données numériques extraites fournissent la courbe seconde par seconde de la vitesse réelle, de la pression d'air à la conduite générale, des crans de traction actionnés par le conducteur et des temps de réaction aux alarmes sonores de la VACMA. Ce dépouillement permet de déterminer avec une certitude scientifique absolue si l'accident est imputable à une défaillance humaine, un défaut mécanique de matériel roulant ou une rupture d'infrastructure de voie."
    )

    # PAGE 8: Rétablissement de la Voie et Reprise du Trafic
    pdf.add_page()
    pdf.render_page_header(8, "Rétablissement de l'Infrastructure et Rouverture", "Travaux de voie d'urgence, marche d'essai et certification")
    pdf.render_section("8.1. Travaux de réhabilitation de la plateforme")
    pdf.render_paragraph(
        "Une fois les véhicules accidentés évacués ou ripés hors du gabarit, les équipes de la Direction des Installations Fixes engagent les travaux de remise en état de la voie : ripage de coupons de rail neufs, remplacement des traverses détruites par des traverses neuves en Azobé créosoté, apport de ballast frais et bourrage manuel puis mécanique de la zone d'impact. L'écartement et le nivellement sont vérifiés avec une tolérance stricte de ± 2 mm par rapport aux normes nominales."
    )
    pdf.render_section("8.2. Marche d'essai et certificat de sécurité")
    pdf.render_paragraph(
        "Avant d'autoriser la réouverture de la ligne commerciale au service régulier des passagers, une circulation d'essai obligatoire est effectuée par une locomotive de ligne circulant isolée sans convoi remorqué. La première marche d'essai s'effectue à vitesse très lente n'excédant pas 15 km/h, le chef de district observant visuellement le comportement des rails sous la charge des essieux. Si aucun tassement n'est décelé, le Certificat d'Aptitude à la Circulation (CAC) est cosigné par le Directeur des Installations Fixes et le Directeur de la Sécurité, autorisant la reprise du trafic sous limitation temporaire de vitesse à 30 km/h pendant 72 heures."
    )

    pdf.output(str(out_pdf_path))
    print(f"[OK] Généré : {out_pdf_path.name} (8 pages)")


# ==============================================================================
# DOCUMENT 5: RDA-EXP-05 - Manuel Exploitation Gares & Aiguillages
# ==============================================================================
def create_doc_5(out_pdf_path: Path):
    pdf = CAMRAILManualPDF("REF: CAMRAIL-RDA-EXP-05 / V4.0", "Manuel d'Exploitation des Gares et Aiguillages")
    
    # PAGE 1: Organisation des Gares
    pdf.add_page()
    pdf.render_page_header(1, "Organisation et Typologie des Gares Ferroviaires", "Hiérarchie des gares, fonctions opérationnelles et missions")
    pdf.render_section("1.1. Classification des gares du réseau CAMRAIL")
    pdf.render_paragraph(
        "Les gares du réseau ferré national CAMRAIL constituent les nœuds fondamentaux de la sécurité des circulations et de la gestion commerciale du transport. Elles sont classées en trois catégories fonctionnelles : les Gares Principales de Bifurcation et de Triage (Douala-Bassa, Yaoundé-Mvolyé, Ngaoundéré) qui assurent la formation des trains de fret, l'entretien des locomotives, l'embarquement massif des passagers et la régulation locale ; les Gares Secondaires de Croisement (Edéa, Eseka, Mbalmayo, Bélabo, Goyoum) équipées d'au moins une voie d'évitement permettant le croisement ou le dépassement des convois sur voie unique ; et les Haltes Voyageurs non gardées destinées uniquement à la montée et descente des voyageurs de proximité."
    )
    pdf.render_section("1.2. Rôles et responsabilités du personnel d'exploitation")
    pdf.render_paragraph(
        "Le Chef de Gare est le représentant exclusif de la Direction Générale dans l'emprise de sa gare. Il exerce l'autorité hiérarchique et réglementaire sur l'ensemble du personnel de service, y compris les aiguilleurs, agents de circulation, facteurs mixtes et équipes de manœuvre. Il est personnellement responsable de la stricte application des règlements de circulation, de la tenue des registres de sécurité, de la surveillance des passages à niveau situés dans sa zone et de la sécurité des quais de voyageurs."
    )

    # PAGE 2: Postes d'Aiguillage et Verrouillage Bouré
    pdf.add_page()
    pdf.render_page_header(2, "Postes d'Aiguillage et Systèmes de Verrouillage", "Commandes mécaniques et électriques, serrures Bouré et sécurité")
    pdf.render_section("2.1. Technologie des postes d'aiguillage")
    pdf.render_paragraph(
        "La manœuvre des aiguillages et des signaux de gare est réalisée au moyen d'installations adaptées à l'importance du trafic de la station. Dans les gares majeures, des Postes tout Relais à Transit Souple (PRS) ou postes électromécaniques permettent la commande centralisée des itinéraires depuis une table de contrôle optique munie de commutateurs d'itinéraires. Dans les gares intermédiaires de ligne, des Postes Mécaniques à Leviers de type Saxby ou des leviers à contrepoids individuels de pied d'aiguille sont manœuvrés manuellement par les aiguilleurs sous les ordres directs du chef de gare."
    )
    pdf.render_section("2.2. Verrouillage mécanique de sécurité par serrures Bouré")
    pdf.render_paragraph(
        "Pour éliminer tout risque d'erreur humaine dans la composition des itinéraires, les aiguillages situés sur la voie principale sont asservis par un système de Verrouillage Bouré à Clés Transférables. Ce système mécanique impose une séquence logique infranchissable : l'aiguilleur ne peut libérer la clé autorisant l'ouverture du signal d'entrée que si l'aiguillage a été préalablement orienté dans la bonne position et que la pointe d'aiguille a été mécaniquement verrouillée sur le rail contre-aiguille. Tout interstice supérieur à 1,5 mm entre la pointe et le contre-rail empêche la rotation de la clé dans la serrure de contrôle."
    )

    # PAGE 3: Dépêches de Cantonnement Téléphonique
    pdf.add_page()
    pdf.render_page_header(3, "Échange Réglementaire des Dépêches de Voie", "Formules de demande et accord de voie libre, registres de gare")
    pdf.render_section("3.1. Structure immuable des dépêches de sécurité")
    pdf.render_paragraph(
        "Sur les sections exploitées en cantonnement téléphonique, l'échange de dépêches constitue l'unique barrière protégeant contre le risque de collision frontale (nez à nez). Les communications entre chefs de gare encadrants doivent être formulées dans un français rigoureux, d'une voix posée, sans recours à l'argot ferroviaire ou aux abréviations verbales. L'utilisation d'enregistreurs téléphoniques automatiques au PCR assure la traçabilité juridique et technique de chaque communication opérationnelle."
    )
    pdf.render_section("3.2. Formule obligatoire de Demande et Accord de Voie Libre")
    pdf.render_paragraph(
        "La Demande de Voie Libre (DVL) est transmise selon la syntaxe suivante : 'Gare d'Edéa demande voie libre à gare de Messondo pour train de voyageurs numéro 182, départ prévu à 08 heures 45'. Le chef de gare destinataire s'assure que le canton est libre de tout convoi, consulte son registre modèle R-1 et répond par la formule d'Accord de Voie Libre (AVL) : 'Gare de Messondo accorde voie libre à gare d'Edéa pour train de voyageurs numéro 182, accord numéro 34'. L'agent demandeur doit immédiatement répéter intégralement mot à mot l'accord reçu avant de délivrer le signal de départ au conducteur."
    )

    # PAGE 4: Croisements et Dépassements en Gare
    pdf.add_page()
    pdf.render_page_header(4, "Organisation des Croisements et Dépassements", "Gestion de la voie unique, priorité de circulation et voies d'évitement")
    pdf.render_section("4.1. Principe de priorité des circulations")
    pdf.render_paragraph(
        "Sur la voie unique du réseau CAMRAIL, les croisements (rencontre de deux trains circulant en sens opposé) et les dépassements (un train rapide doublant un convoi lent circulant dans le même sens) sont programmés par la grille horaire officielle. En cas de perturbation ou de retard, la modification du point de croisement relève de la compétence exclusive du Régulateur du PCR. L'ordre de priorité normal est le suivant : 1. Trains de secours en intervention urgente ; 2. Trains de voyageurs Express Intercity ; 3. Trains omnibus de voyageurs ; 4. Trains lourds d'hydrocarbures et fret conteneurisé ; 5. Trains de ballast et engins de travaux de voie."
    )
    pdf.render_section("4.2. Procédure de réception du convoi sur voie d'évitement")
    pdf.render_paragraph(
        "Le train le moins prioritaire est toujours dirigé en premier sur la voie d'évitement. Le chef de gare trace l'itinéraire vers la voie d'évitement, vérifie le calage de l'aiguille d'entrée et présente le signal d'entrée avertisseur ouvert avec signal de direction. Dès que le convoi est entièrement garé à l'intérieur des repères de garage (dégagement total de la zone de franchissement d'aiguille matérialisée par le piquet de garage blanc), le chef de gare replace immédiatement l'aiguillage en position droite vers la voie principale et verrouille la serrure avant d'ouvrir le signal au train croiseur prioritaire."
    )

    # PAGE 5: Manœuvres de Triage et Sécurité
    pdf.add_page()
    pdf.render_page_header(5, "Sécurité des Manœuvres et Formation des Convois", "Vitesses limites, sabots d'arrêt et protection de la voie principale")
    pdf.render_section("5.1. Réglementation stricte des manœuvres de gare")
    pdf.render_paragraph(
        "Les opérations de manœuvre (découpe de rames, tri des wagons de marchandises par destination, refoulement de voitures voyageurs au dépôt) présentent des risques professionnels élevés pour les agents au sol. La règle d'or dispose qu'aucune manœuvre ne doit jamais empiéter sur la voie principale sans l'accord écrit exprès du Chef de Gare, formalisé par le registre modèle M-4. Les signaux de manœuvre sont transmis par gestes codifiés de jour à l'aide de fanions jaunes ou rouges, et de nuit par des lanternes de manœuvre à verres colorés."
    )
    pdf.render_section("5.2. Vitesses maximales et immobilisation des wagons")
    pdf.render_paragraph(
        "La vitesse maximale autorisée lors des mouvements de manœuvre est strictement limitée à 15 km/h en traction directe, et réduite à 5 km/h lors de l'accostage des véhicules immobiles pour l'opération d'attelage. Tout wagon stationné sur une voie de service ou de triage en pente doit obligatoirement être immobilisé par le serrage de son frein à main mécanique et par la pose d'au moins un sabot d'enrayage en acier forgé calé sous la roue aval. Le refoulement de wagons sans agent de manœuvre posté en tête sur le marchepied de vigie est strictement interdit."
    )

    # PAGE 6: Documents de Circulation et Bulletins Écrits
    pdf.add_page()
    pdf.render_page_header(6, "Ordres Écrits et Bulletins de Circulation", "Bulletin d'ordre C-14, ordre de ralentissement ORV et composition")
    pdf.render_section("6.1. La primauté absolue de l'écrit en exploitation ferroviaire")
    pdf.render_paragraph(
        "Toute dérogation temporaire à la signalisation normale, tout ordre de ralentissement imprévu et toute modification de consigne de sécurité doivent obligatoirement faire l'objet d'un document écrit remis en main propre au conducteur contre émargement sur souche numérotée. Aucun conducteur n'est autorisé à exécuter un ordre de sécurité transmis par téléphone ou radio sans réception physique du document correspondant, à l'exception exclusive des messages d'arrêt d'urgence absolu."
    )
    pdf.render_section("6.2. Typologie des bulletins réglementaires")
    pdf.render_paragraph(
        "Le Bulletin de Franchissement (BF modèle C-14) autorise le dépassement d'un signal d'arrêt absolu défaillant. L'Ordre de Ralentissement de Voie (ORV modèle C-8) notifie au conducteur la présence d'un chantier de voie non protégé par un signal fixe, en précisant le PK de début, le PK de fin et la vitesse plafond autorisée (généralement 20 ou 30 km/h). Le Bulletin de Composition et de Freinage récapitule le tonnage exact du train, le nombre d'essieux, le métrage total de la rame et atteste que le pourcentage réel de freinage calculé est supérieur ou égal au pourcentage minimum requis par le livret de ligne."
    )

    # PAGE 7: Sécurité des Personnes et Usagers en Gare
    pdf.add_page()
    pdf.render_page_header(7, "Sécurité des Quais, Passagers et Riverains", "Canalisation des flux, traversées planchéiées et gabarit")
    pdf.render_section("7.1. Gestion des flux de voyageurs sur les quais")
    pdf.render_paragraph(
        "L'embarquement et le débarquement des passagers dans les gares à forte fréquentation (Douala-Bassa, Yaoundé, Edéa, Ngaoundéré) exigent une organisation rigoureuse pour éviter tout accident corporel aux abords des voies ferrées. Les quais sont peints d'une ligne jaune continue de sécurité située à 1,20 mètre du bord du rail. Les agents de sécurité ferroviaire veillent à ce qu'aucun voyageur ne franchisse cette ligne avant l'arrêt complet du train. L'accès aux marchepieds extérieurs et le voyage dangereux sur les toits des wagons ou entre les tampons d'attelage sont formellement prohibés et passibles de poursuites pénales immédiates."
    )
    pdf.render_section("7.2. Traversées piétonnes des voies en gare")
    pdf.render_paragraph(
        "La traversée des voies par les piétons dans l'emprise des gares ne peut s'effectuer qu'aux Passages Planchéiés pour Piétons (PPP) balisés par des pictogrammes d'interdiction de s'attarder. Avant d'engager la traversée, les usagers doivent regarder à gauche et à droite. Il est strictement interdit de traverser la voie à moins de 20 mètres d'une locomotive en stationnement avec feux allumés ou de passer sous les attelages de wagons en attente. Des barrières grillagées rigides doivent canaliser les flux de passagers depuis le hall de gare jusqu'aux quais de départ."
    )

    # PAGE 8: Archivage, Registres et Relève de Service
    pdf.add_page()
    pdf.render_page_header(8, "Tenue des Archives Réglementaires et Relèves", "Conservation quinquennale, passation de consigne et audits")
    pdf.render_section("8.1. Conservation légale des registres de circulation")
    pdf.render_paragraph(
        "Tous les registres d'exploitation tenus en gare possèdent un statut légal d'actes d'autorité publique en matière de sécurité des transports. Le Registre des Mouvements de Trains (Modèle R-1), le Registre des Dépêches Téléphoniques de Cantonnement (Modèle R-8) et les carnets de souches des bulletins d'ordre (C-14, ORV) doivent être tenus sans rature, surcharge ni blanc correcteur. En fin de chaque journée d'exploitation à minuit, le chef de gare clôture le registre en tirant un trait horizontal à l'encre rouge et appose sa signature et le timbre humide officiel de la gare. Ces registres sont conservés sous clé pendant une durée minimale obligatoire de cinq ans."
    )
    pdf.render_section("8.2. Cérémonie de passation de consigne et relève")
    pdf.render_paragraph(
        "La relève entre l'agent de circulation descendant et l'agent montant fait l'objet d'un protocole minutieux de passation de consignes d'au moins 20 minutes. L'agent sortant informe son collègue de la position exacte de chaque train engagé sur les cantons adjacents, des travaux de voie en cours sur la section, de l'état des appareils de voie sous dérangement et de la présence des clés de sécurité Bouré dans le tableau de verrouillage. La passation est actée par la signature conjointe du Procès-Verbal de Relève au registre de poste."
    )

    pdf.output(str(out_pdf_path))
    print(f"[OK] Généré : {out_pdf_path.name} (8 pages)")


def generate_all_and_index():
    print("=== Démarrage de la génération des 5 manuels CAMRAIL (8 pages chacun) ===")
    
    docs_to_generate = [
        ("Manuel_Securite_Circulation_Ferroviaire_CAMRAIL.pdf", create_doc_1, "RDA-SEC-01 : Manuel Général de Sécurité et de Circulation Ferroviaire", "Sécurité & Circulation", "Direction des Opérations Ferroviaires (DOF)"),
        ("Guide_Maintenance_Superstructure_Voie_CAMRAIL.pdf", create_doc_2, "RDA-MNT-02 : Guide Technique de Maintenance des Voies et Appareils de Voie", "Infrastructure & Voie", "Direction des Installations Fixes (DIF)"),
        ("Reglement_Conduite_Traction_Locomotives_CAMRAIL.pdf", create_doc_3, "RDA-TRC-03 : Règlement Général de Conduite et Matériel de Traction", "Traction & Conduite", "Direction du Matériel Roulant (DMR)"),
        ("Plan_Urgence_Intervention_Accidents_CAMRAIL.pdf", create_doc_4, "RDA-URG-04 : Plan d'Intervention d'Urgence et Secours Ferroviaires", "Urgence & Sécurité", "Direction QHSE et Sécurité Générale"),
        ("Manuel_Exploitation_Gares_Et_Aiguillages_CAMRAIL.pdf", create_doc_5, "RDA-EXP-05 : Manuel d'Exploitation des Gares et Postes d'Aiguillage", "Exploitation des Gares", "Direction des Opérations Ferroviaires (DOF)"),
    ]
    
    db = SessionLocal()
    admin_user = db.query(User).filter(User.role == "admin").first()
    admin_id = admin_user.id if admin_user else 1
    default_group = db.query(SecurityGroup).filter(SecurityGroup.name == "default").all()

    for filename, generator_func, title, category, department in docs_to_generate:
        print(f"\n--- Génération de {filename} ---")
        temp_pdf = STORAGE_DOCS_DIR / f"temp_{filename}"
        generator_func(temp_pdf)
        
        # Read contents and calculate checksum
        with open(temp_pdf, "rb") as f:
            pdf_bytes = f.read()
            
        checksum = hashlib.sha256(pdf_bytes).hexdigest()
        target_storage_path = STORAGE_DOCS_DIR / f"{checksum}.pdf"
        
        # Save to storage with checksum filename
        with open(target_storage_path, "wb") as f:
            f.write(pdf_bytes)
            
        # Also copy to Documentation RailMind Lite with human-readable name
        export_path = DOCS_EXPORT_DIR / filename
        with open(export_path, "wb") as f:
            f.write(pdf_bytes)
            
        if temp_pdf.exists():
            temp_pdf.unlink()
            
        print(f"Fichier stocké : {target_storage_path}")
        print(f"Copie exportée : {export_path}")
        
        # Check if already exists in DB
        existing_doc = db.query(Document).filter(Document.checksum == checksum).first()
        if existing_doc:
            doc = existing_doc
            doc.title = title
            doc.category = category
            doc.department = department
            doc.file_url = str(target_storage_path)
            doc.status = "processing"
            db.commit()
            print(f"Mise à jour du document existant (ID {doc.id})")
        else:
            doc = Document(
                title=title,
                version="1.0",
                category=category,
                department=department,
                effective_date=datetime.now(),
                status="processing",
                file_url=str(target_storage_path),
                checksum=checksum,
                uploaded_by=admin_id
            )
            doc.security_groups = default_group
            db.add(doc)
            db.commit()
            db.refresh(doc)
            print(f"Nouveau document créé (ID {doc.id})")
            
        # Clean existing pages and chunks for this document
        db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()
        db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).delete()
        db.commit()
        
        # Extract native PDF pages with pdfplumber
        extracted_pages = process_document(str(target_storage_path), ".pdf")
        print(f"Pages extraites par pdfplumber : {len(extracted_pages)}")
        assert len(extracted_pages) >= 7, f"Erreur : attendu >= 7 pages, obtenu {len(extracted_pages)}"
        
        for pinfo in extracted_pages:
            p_record = DocumentPage(
                document_id=doc.id,
                page_number=pinfo["page_number"],
                extracted_text=pinfo["text"],
                extraction_method=pinfo["method"]
            )
            db.add(p_record)
        db.commit()
        
        # Index document into chunks with embeddings and French tsvector
        created_chunks = index_document(doc.id, db)
        doc.status = "active"
        db.commit()
        print(f"[SUCCÈS] Document ID {doc.id} ({doc.title}) : {len(extracted_pages)} pages physiques, {created_chunks} chunks indexés.")

    db.close()
    print("\n=== GÉNÉRATION ET INDEXATION COMPLÈTE TERMINÉE AVEC SUCCÈS ===")

if __name__ == "__main__":
    generate_all_and_index()
