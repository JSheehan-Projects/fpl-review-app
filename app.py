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
            # Map the exact API keys to clean, readable column names for the tooltip
            columns_to_keep = {
                'event': 'Gameweek',
                'total_points': 'Total Points',
                'points': 'GW Points',
                'overall_rank': 'Overall Rank',
                'bank': 'Bank (£m)',
                'event_transfers': 'Transfers',
                'event_transfers_cost': 'Hit Cost',
                'points_on_bench': 'Bench Points'
            }
            # Filter the dataframe and rename the columns
            df = df[list(columns_to_keep.keys())].rename(columns=columns_to_keep)
            
            # Divide bank by 10 to reflect true £m value
            df['Bank (£m)'] = df['Bank (£m)'] / 10
            
            return df
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_manager_name(manager_id):
    """Fetches the real name and team name for a specific manager ID."""
    url = f"{BASE_URL}/entry/{manager_id}/"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        player_name = f"{data.get('player_first_name', '')} {data.get('player_last_name', '')}".strip()
        team_name = data.get('name', 'Unknown Team')
        return f"{player_name} ({team_name})"
    return f"Manager ID: {manager_id}"

@st.cache_data(ttl=3600)
def get_manager_leagues(manager_id):
    """Fetches the private classic leagues a manager is in."""
    url = f"{BASE_URL}/entry/{manager_id}/"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        leagues = data.get('leagues', {}).get('classic', [])
        return {league['name']: league['id'] for league in leagues if league['league_type'] == 'x'}
    return {}

@st.cache_data(ttl=3600)
def get_league_managers(league_id, limit=10):
    """Fetches the top managers in a classic league with real names and team names."""
    url = f"{BASE_URL}/leagues-classic/{league_id}/standings/"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        standings = data.get('standings', {}).get('results', [])
        return {
            manager['entry']: f"{manager['player_name']} ({manager['entry_name']})" 
            for manager in standings[:limit]
        }
    return {}

# Input FPL ID
main_id = st.text_input("Enter your FPL ID:", value="")

if main_id:
    # Fetch leagues for the drop-down menu
    leagues_dict = get_manager_leagues(main_id)
    
    if not leagues_dict:
        st.warning("Could not find any private leagues for this ID. Showing individual data only.")
        league_options = ["Just my team"]
    else:
        league_options = ["Just my team"] + list(leagues_dict.keys())
    
    selected_league = st.selectbox("Compare against a league (Top 10 managers)", league_options)
    
    plot_data = []
    
    # Fetch the main user's data
    df_main = get_manager_history(main_id)
    if not df_main.empty:
        df_main['Manager'] = get_manager_name(main_id)
        plot_data.append(df_main)
            
    # Fetch league managers if applicable
    if selected_league != "Just my team":
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

    if plot_data:
        final_df = pd.concat(plot_data, ignore_index=True)
        
        # Filter out non-competitive players using a multiselect filter
        all_managers = final_df['Manager'].unique().tolist()
        selected_managers = st.multiselect(
            "Filter Managers:", 
            options=all_managers, 
            default=all_managers,
            help="Untick managers to remove them from the chart entirely."
        )
        
        filtered_df = final_df[final_df['Manager'].isin(selected_managers)]
        
        if not filtered_df.empty:
            # We add hover_data here to tell Plotly to display our new columns
            fig = px.line(
                filtered_df, 
                x="Gameweek", 
                y="Total Points", 
                color="Manager", 
                markers=True, 
                hover_data={
                    "Manager": True,
                    "Gameweek": True,
                    "Total Points": True,
                    "GW Points": True,
                    "Overall Rank": ":,", # The :, automatically formats with commas
                    "Bank (£m)": ":.1f",  # The :.1f forces one decimal place (e.g., 0.0)
                    "Transfers": True,
                    "Hit Cost": True,
                    "Bench Points": True
                },
                title=f"Total Points Evolution - {selected_league if selected_league != 'Just my team' else 'Individual'}"
            )
            
            # Fix X-axis to start exactly at Gameweek 1 and avoid negative/zero values
            max_gw = int(filtered_df['Gameweek'].max())
            fig.update_layout(
                xaxis=dict(
                    tickmode='linear', 
                    dtick=1,
                    range=[1, max_gw]
                )
            ) 
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Please select at least one manager to display the graph.")
    else:
        st.warning("No data found. Please check the FPL ID.")