import dash
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import os.path

#from dash import Dash
#from dash import dash


from app import app 
from components.engine import functions
from components.layout.home import * 
import numpy as np
import pandas as pd
import components.layout.home as home
import components.layout.about_us as about_us
import components.layout.ressources as ressources
import components.layout.summary as summary
from time import sleep


import dash_bootstrap_components as dbc

from app import server

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    prevent_initial_callbacks=True,
    title="Museme",
    update_title="Museme · …",
)


app.config.suppress_callback_exceptions = True
server = app.server


app.layout = html.Div([
    
    dcc.Location(id="url"),
    
    menu_dropdown,
    
    content

])



#fonctionnement de la sidebar
@app.callback(Output("page-content", "children"),
              [Input("url", component_property="pathname")])

def render_page_content(pathname):
    if pathname == "/":
        return home.layout
    elif pathname == "/page-1":
        return  summary.layout
    elif pathname == "/page-2":
        return about_us.layout
    elif pathname == "/page-3":
        return ressources.layout


@app.callback(Output("example-output", "children"), 
              [Input("onboarding-button", "n_clicks")])

def on_button_click(n):
    if n is None:
        return "Not clicked."
    else:
        return f"Clicked {n} times."

@app.callback(Output(component_id='record-title', component_property='style'),
             Output(component_id='background-video-first-page', component_property='style'),
             Output(component_id='onboarding-explanation', component_property='style'),
             Output(component_id='onboarding-button', component_property='style'),
             [Input(component_id="onboarding-button", component_property='n_clicks')])

def hide_onb_style(n):
    if n is not None:
        return [{'display':'none'}, {'display':'none'},{'display':'none'},{'display':'none'}]

@app.callback(Output(component_id='input-dropdown-content', component_property='children'),
              [Input(component_id="onboarding-button", component_property='n_clicks')]) 

def display_dropdown_layout(n):
    if n is not None:
        return display_dropdown_onboarding()


@app.callback(Output('title-dropdown', 'options'),
    [Input('artist-dropdown', 'value')])

def display_titles_dropdown (artist_dropdown):
  df_input=functions.load_catalog()
  # La valeur est le numero de ligne, pas le titre : 54 titres existent chez
  # plusieurs artistes. Sans artiste choisi, tous les titres sont proposes.
  if artist_dropdown is None:
      df_title=df_input.drop_duplicates(subset=['Song', 'Artist']).sort_values(by=['Song'])
      return [{'label': f'{row.Song} — {row.Artist}', 'value': int(i)} for i, row in df_title.iterrows()]
  df_title=df_input[df_input['Artist']==artist_dropdown]
  df_title=df_title.drop_duplicates(subset=['Song']).sort_values(by=['Song'])
  return [{'label': song, 'value': int(i)} for i, song in df_title['Song'].items()]



@app.callback(Output(component_id='output-content-upload', component_property='children'),
              [Input(component_id='title-dropdown', component_property='value')]) 

def update_output(song_input):
    if song_input is not None:
        track_info=functions.input_data_extraction(song_input)
        return audio_play_layout(track_info)
    else:
        pass

@app.callback(Output(component_id='output-recommendation-upload', component_property='children'),
              [Input(component_id='title-dropdown', component_property='value')])

def show_recommendations(song_info):
    if song_info is not None:
        results=functions.recommandation_cosine(song_info)
        return recommendation_box_layout(results)
    else:
        pass

#callback pour cacher les layout

# @app.callback(Output(component_id='record-title', component_property='style'),
#              Output(component_id='background-video-first-page', component_property='style'),
#              #Output(component_id='pick_audio_input', component_property='style'),
#              [Input(component_id='title-dropdown', component_property='value')])

# def hide_style(song_input):
#     if song_input is not None:
#         return [{'display':'none'}, {'display':'none'}]
#     else: 
#         pass


# @app.callback(Output(component_id='output-tempo-upload', component_property='children'), #Output(component_id='output-graph-upload', component_property='children'),
#               [Input(component_id='title-dropdown', component_property='value')]) #deuxieme input associe le deuxieme parametre de la focnction

# def download_preview_and_analyze(song_input):
#     if song_input is not None:
#         #track_genre=record[4]
#         track_genre='unknown'
#         return preview_analysis_layout(track_genre)
#     else:
#         pass

# @app.callback(Output(component_id='output-recommendation-upload', component_property='children'),
#               [Input(component_id='recordings', component_property='children')])

# def show_recommendations(record):
#     if record is not None:
#         track_title=record[1]
#         track_artist=record[0]
#         #track_genre=record[4]
#         track_coverimg=record[2]
#         url_preview=record[3]
#         id_preview=url_preview.split('/')
#         id_preview=id_preview[-1]
#         destination= os.path.join("audio/preview_to_analyze/", id_preview)
#         wget.download(url_preview, out=destination) 
#         ####
#         sound = AudioSegment.from_file(destination,sr=22050)
#         y = AudioSegment.get_array_of_samples(sound)
#         y = np.array(y).astype(float)
#         #####
#         df_for_rec=functions.analyze_music_reco(y=y, track_artist=track_artist, track_title=track_title, track_genre='genre',track_coverimg_hq=track_coverimg, audio_preview=url_preview)
#         df_for_rec=functions.recommandation_cosine(df_for_rec)
#         return recommendation_box_layout(df_for_rec)
#     else:
#         pass

if __name__ == '__main__':
    app.run(port=8050, debug=True)