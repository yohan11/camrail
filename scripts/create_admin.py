#!/usr/bin/env python3
"""
Script de création sécurisée d'un compte administrateur en production.
Usage interactif :
    python scripts/create_admin.py

Usage avec arguments (automatisation / CI) :
    python scripts/create_admin.py --email admin@domaine.cm --name "Admin Nom" --password "SuperSecret1234!"
"""

import sys
import os
import argparse
import getpass
import re

# Ajouter le dossier backend au PYTHONPATH
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.database import SessionLocal
from app.models.schemas import User, SecurityGroup, UserRole
from app.security import hash_password

TRIVIAL_PASSWORDS = {
    "adminpassword",
    "password1234",
    "password12345",
    "123456789012",
    "changeme1234",
    "railmind2026",
    "adminadmin123",
    "qwertyuiop12",
    "azertyuiop12",
}

def validate_password_strength(password: str) -> None:
    if len(password) < 12:
        raise ValueError("Le mot de passe doit comporter au moins 12 caractères.")
    
    if password.lower() in TRIVIAL_PASSWORDS:
        raise ValueError("Ce mot de passe est trop trivial ou fait partie des mots de passe par défaut interdits.")
        
    if len(set(password)) <= 3:
        raise ValueError("Le mot de passe est trop simple (trop de caractères répétés).")

def validate_email(email: str) -> None:
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ValueError(f"Format d'adresse email invalide : {email}")

def create_admin(email: str, full_name: str, password: str):
    validate_email(email)
    validate_password_strength(password)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.lower()).first()
        hashed_pwd = hash_password(password)

        if user:
            print(f"L'utilisateur {email} existe déjà. Mise à jour vers le rôle administrateur et renouvellement du mot de passe...")
            user.password_hash = hashed_pwd
            user.role = UserRole.ADMIN
            user.full_name = full_name
            user.is_active = True
        else:
            print(f"Création d'un nouvel administrateur : {email}")
            user = User(
                email=email.lower(),
                password_hash=hashed_pwd,
                full_name=full_name,
                role=UserRole.ADMIN,
                is_active=True
            )
            default_group = db.query(SecurityGroup).filter(SecurityGroup.name == "default").first()
            if default_group:
                user.security_groups.append(default_group)
            db.add(user)

        db.commit()
        db.refresh(user)
        print("=" * 60)
        print(f"Compte administrateur configuré avec succès : {user.email} (ID: {user.id})")
        print("=" * 60)
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description="Créer un administrateur RailMind Lite pour la production")
    parser.add_argument("--email", help="Adresse email de l'administrateur")
    parser.add_argument("--name", help="Nom complet de l'administrateur")
    parser.add_argument("--password", help="Mot de passe (optionnel, sinon saisie masquée)")
    args = parser.parse_args()

    print("=== Création du compte administrateur RailMind Lite ===")
    
    email = args.email
    while not email:
        email = input("Adresse email de l'administrateur : ").strip()
        try:
            validate_email(email)
        except ValueError as e:
            print(f"Erreur : {e}")
            email = None

    full_name = args.name
    while not full_name:
        full_name = input("Nom complet de l'administrateur : ").strip()

    password = args.password
    while not password:
        pwd1 = getpass.getpass("Mot de passe (>= 12 caractères) : ")
        try:
            validate_password_strength(pwd1)
        except ValueError as e:
            print(f"Erreur : {e}")
            continue

        pwd2 = getpass.getpass("Confirmez le mot de passe : ")
        if pwd1 != pwd2:
            print("Erreur : Les deux mots de passe ne correspondent pas.")
            continue
        password = pwd1

    try:
        create_admin(email=email, full_name=full_name, password=password)
    except Exception as e:
        print(f"ERREUR : Impossible de créer le compte administrateur : {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
