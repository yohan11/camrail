import re
from typing import Tuple

# 1. Images markdown : ![alt](url)
MARKDOWN_IMAGE_REGEX = re.compile(r'!\[.*?\]\(.*?\)', re.DOTALL)

# 2. Balises HTML complètes : <tag ...>, </tag>, <tag .../>
HTML_TAG_REGEX = re.compile(r'<[^>]+>', re.DOTALL)

# 3. Liens markdown vers des URLs externes : [texte](http...)
MARKDOWN_LINK_REGEX = re.compile(r'\[([^\]]+)\]\((?:https?://|ftp://|data:|javascript:|www\.)[^)]*\)', re.IGNORECASE)

# 4. URLs brutes restantes (http, https, ftp, data:, javascript:, www.)
RAW_URL_REGEX = re.compile(r'(?:https?://|ftp://|data:|javascript:|\bwww\.)[^\s<>"\'\)\]\}]+', re.IGNORECASE)


def sanitize_answer(text: str) -> Tuple[str, int]:
    """
    Nettoie la réponse générée par le modèle pour empêcher toute exfiltration de données
    ou injection de contenu actif/externe (liens, images, iframes, HTML, scripts).
    
    Règles de sécurité :
    - Supprime les images markdown ![...](...)
    - Supprime toute balise HTML (<img ...>, <script>, <iframe>, <a ...>, etc.)
    - Transforme les liens markdown [texte](http...) en simple texte "texte"
    - Remplace toute URL brute (http://, https://, ftp://, www., data:, javascript:) par "[lien retiré]"
    - Ne touche JAMAIS aux marqueurs de citation documentaire [1], [2], [1, 2], [12], etc.
    
    Retourne : (texte_propre, nb_éléments_retirés)
    """
    if not text:
        return "", 0

    removed_count = 0

    # 1. Suppression des images markdown (vecteur direct d'exfiltration)
    images_found = len(MARKDOWN_IMAGE_REGEX.findall(text))
    if images_found > 0:
        removed_count += images_found
        text = MARKDOWN_IMAGE_REGEX.sub('', text)

    # 2. Suppression de toutes les balises HTML
    html_found = len(HTML_TAG_REGEX.findall(text))
    if html_found > 0:
        removed_count += html_found
        text = HTML_TAG_REGEX.sub('', text)

    # 3. Transformation des liens markdown en simple texte
    links_found = len(MARKDOWN_LINK_REGEX.findall(text))
    if links_found > 0:
        removed_count += links_found
        text = MARKDOWN_LINK_REGEX.sub(r'\1', text)

    # 4. Remplacement des URLs brutes restantes par [lien retiré]
    urls_found = len(RAW_URL_REGEX.findall(text))
    if urls_found > 0:
        removed_count += urls_found
        text = RAW_URL_REGEX.sub('[lien retiré]', text)

    return text, removed_count
