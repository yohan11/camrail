# Guide de Préparation et Transfert Hors-Ligne d'Ollama (Air-Gapped)

Pour respecter les exigences strictes de confidentialité et de souveraineté des données de **CAMRAIL**, le serveur de production ne dispose d'aucun accès à Internet. Ce document explique la procédure pour préparer les modèles LLM sur une machine connectée, puis les transférer sur le serveur isolé.

---

## 1. Prérequis sur la Machine Connectée (Avec Internet)

1. Installer Ollama : [https://ollama.com](https://ollama.com)
2. Télécharger le modèle recommandé pour CAMRAIL RailMind Lite :
   ```bash
   ollama pull llama3.2:3b
   ```
3. *(Optionnel)* Si vous prévoyez d'utiliser un modèle alternatif (ex: `mistral:7b` ou `qwen2.5:3b`) :
   ```bash
   ollama pull mistral:7b
   ```

---

## 2. Emplacement des Modèles Ollama

Ollama stocke ses modèles (manifests et blobs de poids) dans un dossier dédié selon le système d'exploitation :

| Système d'exploitation | Chemin par défaut des modèles |
| :--- | :--- |
| **Linux (service standard)** | `/usr/share/ollama/.ollama/models` |
| **Linux (utilisateur standard)**| `~/.ollama/models` |
| **Windows** | `C:\Users\<VotreNomUtilisateur>\.ollama\models` |
| **macOS** | `~/.ollama/models` |

Le dossier `models` contient deux sous-dossiers indispensables :
- `blobs/` : Les poids et tenseurs binaires du modèle GGUF.
- `manifests/` : Les métadonnées et configurations des modèles.

---

## 3. Archivage et Exportation

### Sur Linux / macOS :
```bash
# Se placer dans le dossier racine Ollama
cd ~/.ollama   # ou cd /usr/share/ollama/.ollama

# Créer une archive compressée du dossier models
tar -czvf ollama_models_camrail.tar.gz models/
```

### Sur Windows (PowerShell) :
```powershell
Compress-Archive -Path "$env:USERPROFILE\.ollama\models" -DestinationPath "ollama_models_camrail.zip"
```

Transférez ensuite l'archive (`ollama_models_camrail.tar.gz` ou `.zip`) sur le serveur hors-ligne via support amovible sécurisé (clé USB chiffrée ou transfert réseau interne isolé).

---

## 4. Déploiement sur le Serveur Hors-Ligne (Sans Internet)

### Étape 1 : Installer le binaire Ollama
Transférez l'exécutable d'installation Ollama (téléchargé au préalable) et installez-le sur le serveur.

### Étape 2 : Restaurer le dossier `models`
Décompressez l'archive à l'emplacement approprié :

#### Sur Linux :
```bash
# Arrêter le service Ollama s'il tourne
sudo systemctl stop ollama

# Restaurer le dossier
sudo mkdir -p /usr/share/ollama/.ollama
sudo tar -xzvf ollama_models_camrail.tar.gz -C /usr/share/ollama/.ollama/
sudo chown -R ollama:ollama /usr/share/ollama/.ollama

# Redémarrer Ollama
sudo systemctl start ollama
```

#### Sur Windows :
Décompressez le dossier `models` dans `C:\Users\<UtilisateurSession>\.ollama\models`.

> **Astuce (Dossier personnalisé) :**
> Si vous souhaitez stocker les modèles sur un disque spécifique, définissez la variable d'environnement système :
> - Linux : `Environment="OLLAMA_MODELS=/chemin/vers/disque/models"` dans `/etc/systemd/system/ollama.service`
> - Windows : `setx OLLAMA_MODELS "D:\ollama_models"`

---

## 5. Validation du Fonctionnement Hors-Ligne

Sur le serveur hors-ligne, vérifiez qu'aucun appel réseau n'est nécessaire :

1. Lister les modèles disponibles localement :
   ```bash
   ollama list
   ```
   Vous devez voir apparaître :
   ```text
   NAME            ID              SIZE      MODIFIED
   llama3.2:3b     a80c4f17acd5    2.0 GB    ...
   ```

2. Tester une inférence en ligne de commande locale :
   ```bash
   ollama run llama3.2:3b "Bonjour, es-tu opérationnel hors-ligne ?"
   ```

3. Vérifier que l'API locale répond sur le port 11434 :
   ```bash
   curl http://localhost:11434/api/tags
   ```

Ollama est prêt à alimenter le moteur RAG CAMRAIL RailMind Lite en totale autarcie.
