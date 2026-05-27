import streamlit as st
import requests
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="FPL Points Tracker", layout="wide")
st.title("FPL Total Points Evolution")

BASE_URL = "https://fantasy.premierleague.com/api"
HEADERS = {"User-Agent": "Mozilla/5.0"}

@st.cache_data(ttl=3600)
def get_manager_history(manager_id):
    """Fetches gameweek history for a given manager ID."""
    url = f"{BASE_URL}/entry/{manager_id}/history/"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame(data.get('current', []))
        if not df.empty:
            return df[['event', 'total_points']].rename(columns={'event': 'Gameweek', 'total_points': 'Total Points'})
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_manager_leagues(manager_id):
    """Fetches the private classic leagues a manager is in."""
    url = f"{BASE_URL}/entry/{manager_id}/"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        leagues = data.get('leagues', {}).get('classic', [])
        # 'x' filters for private leagues, removing the massive global ones
        return {league['name']: league['id'] for league in leagues if league['league_type'] == 'x'}
    return {}

@st.cache_data(ttl=3600)
def get_league_managers(league_id, limit=10):
    """Fetches the top managers in a classic league."""
    url = f"{BASE_URL}/leagues-classic/{league_id}/standings/"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        standings = data.get('standings', {}).get('results', [])
        return {manager['entry']: manager['entry_name'] for manager in standings[:limit]}
    return {}

# UI Inputs
col1, col2 = st.columns(2)
with col1:
    main_id = st.text_input("Your FPL ID", value="20123")
with col2:
    compare_id = st.text_input("Comparison FPL ID (Optional)", value="5583436")

if main_id:
    # Fetch leagues for the drop-down menu
    leagues_dict = get_manager_leagues(main_id)
    league_options = ["None (Just compare IDs)"] + list(leagues_dict.keys())
    
    selected_league = st.selectbox("Compare against a league (Top 10 managers)", league_options)
    
    plot_data = []
    
    # Fetch the main user's data
    df_main = get_manager_history(main_id)
    if not df_main.empty:
        df_main['Manager'] = f"Main ID: {main_id}"
        plot_data.append(df_main)
        
    # Fetch comparison ID if no league is selected or as an additional line
    if compare_id and selected_league == "None (Just compare IDs)":
        df_comp = get_manager_history(compare_id)
        if not df_comp.empty:
            df_comp['Manager'] = f"Comparison ID: {compare_id}"
            plot_data.append(df_comp)
            
    # Fetch and append league managers if a league is selected
    if selected_league != "None (Just compare IDs)":
        league_id = leagues_dict[selected_league]
        league_managers = get_league_managers(league_id)
        
        progress_bar = st.progress(0, text="Fetching league history...")
        
        for i, (mgr_id, mgr_name) in enumerate(league_managers.items()):
            if str(mgr_id) != str(main_id): 
                df_mgr = get_manager_history(mgr_id)
                if not df_mgr.empty:
                    df_mgr['Manager'] = mgr_name
                    plot_data.append(df_mgr)
            progress_bar.progress((i + 1) / len(league_managers), text="Fetching league history...")
        progress_bar.empty()

    # Visualise the data
    if plot_data:
        final_df = pd.concat(plot_data, ignore_index=True)
        fig = px.line(
            final_df, 
            x="Gameweek", 
            y="Total Points", 
            color="Manager", 
            markers=True, 
            title=f"Total Points Evolution - {selected_league if selected_league != 'None (Just compare IDs)' else 'Head to Head'}"
        )
        # Force the X-axis to show integers for Gameweeks
        fig.update_layout(xaxis=dict(tickmode='linear', dtick=1)) 
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No data found. Please check the FPL IDs.")