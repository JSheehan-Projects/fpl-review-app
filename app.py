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
            df = df[list(columns_to_keep.keys())].rename(columns=columns_to_keep)
            df['Bank (£m)'] = df['Bank (£m)'] / 10
            return df
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_manager_transfers(manager_id):
    """Fetches all transfers for a given manager ID."""
    url = f"{BASE_URL}/entry/{manager_id}/transfers/"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame(data)
        if not df.empty:
            df['time'] = pd.to_datetime(df['time'])
            return df[['event', 'time']]
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_gameweek_deadlines():
    """Fetches the official deadline time for every gameweek."""
    url = f"{BASE_URL}/bootstrap-static/"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        events = pd.DataFrame(data.get('events', []))
        if not events.empty:
            # 'id' is the gameweek number in this endpoint
            df = events[['id', 'deadline_time']].rename(columns={'id': 'Gameweek'})
            df['deadline_time'] = pd.to_datetime(df['deadline_time'])
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
    manager_name_to_id = {} 
    
    # Fetch the main user's data
    df_main = get_manager_history(main_id)
    if not df_main.empty:
        main_name = get_manager_name(main_id)
        df_main['Manager'] = main_name
        plot_data.append(df_main)
        manager_name_to_id[main_name] = main_id
            
    # Fetch league managers if applicable
    if selected_league != "Just my team":
        league_id = leagues_dict[selected_league]
        league_managers = get_league_managers(league_id)
        
        progress_bar = st.progress(0, text="Fetching league history...")
        for i, (mgr_id, mgr_name) in enumerate(league_managers.items()):
            manager_name_to_id[mgr_name] = mgr_id 
            if str(mgr_id) != str(main_id): 
                df_mgr = get_manager_history(mgr_id)
                if not df_mgr.empty:
                    df_mgr['Manager'] = mgr_name
                    plot_data.append(df_mgr)
            progress_bar.progress((i + 1) / len(league_managers), text="Fetching league history...")
        progress_bar.empty()

    if plot_data:
        final_df = pd.concat(plot_data, ignore_index=True)
        max_gw = int(final_df['Gameweek'].max())
        
        # Filter out non-competitive players
        all_managers = final_df['Manager'].unique().tolist()
        selected_managers = st.multiselect(
            "Filter Managers:", 
            options=all_managers, 
            default=all_managers,
            help="Untick managers to remove them from all charts."
        )
        
        filtered_df = final_df[final_df['Manager'].isin(selected_managers)]
        
        if not filtered_df.empty:
            # --- GRAPH 1: TOTAL POINTS ---
            fig_points = px.line(
                filtered_df, 
                x="Gameweek", 
                y="Total Points", 
                color="Manager", 
                markers=True, 
                hover_data={
                    "Manager": True, "Gameweek": True, "Total Points": True,
                    "GW Points": True, "Overall Rank": ":,", "Bank (£m)": ":.1f",
                    "Transfers": True, "Hit Cost": True, "Bench Points": True
                },
                title=f"Total Points Evolution - {selected_league if selected_league != 'Just my team' else 'Individual'}"
            )
            fig_points.update_layout(xaxis=dict(tickmode='linear', dtick=1, range=[1, max_gw])) 
            st.plotly_chart(fig_points, use_container_width=True)

            # --- FETCH TRANSFER & DEADLINE DATA ---
            st.subheader("Transfer Timing Analysis")
            transfer_list = []
            
            with st.spinner("Fetching transfer data and official deadlines..."):
                deadlines_df = get_gameweek_deadlines()
                
                for mgr_name in selected_managers:
                    mgr_id = manager_name_to_id[mgr_name]
                    df_trans = get_manager_transfers(mgr_id)
                    if not df_trans.empty:
                        df_trans['Manager'] = mgr_name
                        transfer_list.append(df_trans)
            
            if transfer_list and not deadlines_df.empty:
                all_transfers = pd.concat(transfer_list, ignore_index=True)
                all_transfers.rename(columns={'event': 'Gameweek'}, inplace=True)
                
                # Merge official deadlines with the transfers
                all_transfers = pd.merge(all_transfers, deadlines_df, on='Gameweek', how='inner')
                
                # Calculate hours BEFORE the official deadline
                all_transfers['Hours Before Deadline'] = (all_transfers['deadline_time'] - all_transfers['time']).dt.total_seconds() / 3600

                # --- GRAPH 2: INDIVIDUAL TRANSFERS SCATTER PLOT ---
                fig_scatter = px.scatter(
                    all_transfers, 
                    x="Gameweek", 
                    y="Hours Before Deadline", 
                    color="Manager",
                    hover_data={
                        "time": True,
                        "deadline_time": True,
                        "Hours Before Deadline": ":.1f"
                    },
                    title="All Transfers: Hours Prior to the Official Gameweek Deadline"
                )
                fig_scatter.update_layout(xaxis=dict(tickmode='linear', dtick=1, range=[1, max_gw]))
                st.plotly_chart(fig_scatter, use_container_width=True)

                # --- GRAPH 3: AVERAGE TRANSFER TIME LINE PLOT ---
                avg_transfers = all_transfers.groupby(['Manager', 'Gameweek'])['Hours Before Deadline'].mean().reset_index()
                
                gw_range = pd.DataFrame({'Gameweek': range(1, max_gw + 1)})
                mgr_range = pd.DataFrame({'Manager': selected_managers})
                
                grid = pd.merge(mgr_range.assign(key=1), gw_range.assign(key=1), on='key').drop('key', axis=1)
                final_avg_df = pd.merge(grid, avg_transfers, on=['Manager', 'Gameweek'], how='left')

                fig_line = px.line(
                    final_avg_df, 
                    x="Gameweek", 
                    y="Hours Before Deadline", 
                    color="Manager",
                    markers=True,
                    title="Average Transfer Timing per Gameweek (Breaks on zero transfers)"
                )
                fig_line.update_traces(connectgaps=False) 
                fig_line.update_layout(xaxis=dict(tickmode='linear', dtick=1, range=[1, max_gw]))
                st.plotly_chart(fig_line, use_container_width=True)

            else:
                st.info("No transfer data found for the selected managers yet.")
        else:
            st.warning("Please select at least one manager to display the graphs.")
    else:
        st.warning("No data found. Please check the FPL ID.")