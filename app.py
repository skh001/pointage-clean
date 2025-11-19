import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- 1. LISTE DES EMPLOYÉS (CONFIGURATION) ---
# Vous pouvez ajouter ou modifier des noms ici simplement
EMPLOYEES = {
    "1": "Sofiane",
    "2": "Killian",
    "3": "Erwan",
    "4": "Elise"
}

# --- CONFIGURATION GOOGLE SHEETS ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_google_sheet_client():
    try:
        key_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(key_dict, scopes=SCOPES)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Erreur de connexion Google : {e}")
        return None

def load_data():
    client = get_google_sheet_client()
    if client:
        try:
            sh = client.open("PointageDB")
            worksheet = sh.sheet1
            data = worksheet.get_all_records()
            df = pd.DataFrame(data)
            if df.empty:
                return pd.DataFrame(columns=["EmployeID", "Date", "Heure", "Type", "Timestamp"])
            
            # On force la colonne EmployeID en texte pour que "1" soit bien égal à "1"
            df['EmployeID'] = df['EmployeID'].astype(str)
            return df
        except gspread.exceptions.SpreadsheetNotFound:
            st.error("Fichier 'PointageDB' introuvable.")
            return pd.DataFrame()
    return pd.DataFrame()

def save_pointage(employe_id, action_type):
    client = get_google_sheet_client()
    if client:
        now = datetime.now()
        new_row = [
            str(employe_id),
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            action_type,
            now.isoformat()
        ]
        sh = client.open("PointageDB")
        worksheet = sh.sheet1
        worksheet.append_row(new_row)
        return now.strftime("%H:%M:%S")
    return None

def calculate_daily_hours(df):
    """Calcule les heures travaillées et ajoute les Noms"""
    if df.empty:
        return pd.DataFrame()

    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    # Tri important pour que le calcul se fasse dans l'ordre
    df = df.sort_values(by=['EmployeID', 'Timestamp'])
    
    results = []
    
    # On groupe par ID et par Jour
    for (emp_id, date), group in df.groupby(['EmployeID', 'Date']):
        total_seconds = 0
        last_entry = None
        entries_log = [] # Pour vérifier visuellement
        
        for _, row in group.iterrows():
            if row['Type'] == 'Entrée':
                last_entry = row['Timestamp']
                entries_log.append(f"Entrée: {row['Heure']}")
            elif row['Type'] == 'Sortie' and last_entry is not None:
                # C'est ici que le calcul se fait (Heure Fin - Heure Début)
                duration = (row['Timestamp'] - last_entry).total_seconds()
                total_seconds += duration
                entries_log.append(f"Sortie: {row['Heure']}")
                last_entry = None
        
        hours = total_seconds / 3600
        
        # On récupère le nom depuis notre liste au début du code
        nom_employe = EMPLOYEES.get(str(emp_id), "Inconnu")
        
        results.append({
            "Nom": nom_employe,
            "Date": date,
            "Heures Travaillées": round(hours, 2),
            "Détails": " > ".join(entries_log)
        })

    return pd.DataFrame(results)

# --- INTERFACE UTILISATEUR ---

st.set_page_config(page_title="Pointage Cloud FB", page_icon="☁️")
st.title("FRITES BONNEL")

# Saisie de l'ID
employe_id = st.text_input("Numéro d'employé :", max_chars=10)

# Si un ID est entré, on vérifie qui c'est
if employe_id:
    # On cherche le nom dans la liste
    nom = EMPLOYEES.get(employe_id)
    
    if nom:
        st.success(f"Bonjour **{nom}** 👋")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🟢 POINTER ENTRÉE", use_container_width=True):
                with st.spinner('Envoi...'):
                    heure = save_pointage(employe_id, "Entrée")
                if heure: st.success(f"✅ Entrée enregistrée à {heure}")
                
        with col2:
            if st.button("🔴 POINTER SORTIE", use_container_width=True):
                with st.spinner('Envoi...'):
                    heure = save_pointage(employe_id, "Sortie")
                if heure: st.warning(f"🛑 Sortie enregistrée à {heure}")

        # Historique rapide
        st.divider()
        st.caption(f"Historique récent pour {nom} :")
        df = load_data()
        if not df.empty:
            # Filtrer pour cet employé
            history = df[df['EmployeID'] == str(employe_id)].tail(5).sort_values(by='Timestamp', ascending=False)
            st.dataframe(history[['Date', 'Heure', 'Type']], use_container_width=True, hide_index=True)
            
    else:
        st.error("Numéro d'employé inconnu. Vérifiez votre ID.")

# --- ADMIN (Rapport des heures) ---
st.divider()
with st.expander("🔐 Administration & Paie"):
    st.write("Cliquez ci-dessous pour calculer le total des heures par personne.")
    
    if st.button("📊 Calculer le Rapport des Heures"):
        with st.spinner("Calcul en cours..."):
            df_all = load_data()
            if not df_all.empty:
                # Le calcul se fait ici
                rapport = calculate_daily_hours(df_all)
                
                if not rapport.empty:
                    # Affichage du tableau propre
                    st.dataframe(
                        rapport, 
                        use_container_width=True,
                        column_config={
                            "Heures Travaillées": st.column_config.NumberColumn(
                                "Total Heures",
                                format="%.2f h" # Affiche "3.50 h"
                            )
                        }
                    )
                    
                    # Total global par personne (Bonus)
                    st.caption("Total cumulé par personne :")
                    total_par_personne = rapport.groupby("Nom")["Heures Travaillées"].sum().reset_index()
                    st.dataframe(total_par_personne, use_container_width=True)
                    
                else:
                    st.info("Pas assez de données (paires Entrée/Sortie) pour calculer.")
            else:
                st.info("La base de données est vide.")
