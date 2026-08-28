from dash import html
import dash_bootstrap_components as dbc
from dash import dcc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import os.path
import pandas as pd
from app import app 
from components.engine import functions

menu_dropdown = html.Div(
                [           
                    dbc.DropdownMenu(
                        [
                            dbc.DropdownMenuItem("Our app", href="/", active="exact",style={'color':'#f3f3f2','font-weight': 'bold'}),
                            dbc.DropdownMenuItem("Summary", href="/page-1", active="exact"),
                            dbc.DropdownMenuItem("About us", href="/page-2", active="exact"),
                            dbc.DropdownMenuItem("Resources", href="/page-3", active="exact"),
                        ],label="Menu"),

                ],className='menu-button')
"""
logo_header = html.Div(
                 [
                    dbc.Col(
                         html.Img(src='assets/images/Logo_Museme_white.png',className='logo-header'),
                     ),
                     dbc.Col(
                         html.H1('Museme',className='name-header'),
                     )
                 ],className='brand-header' )  
"""
content = html.Div(id="page-content")

background_video = html.Video(id="background-video-first-page",
                            src="assets/videos/background.mp4",
                            autoPlay=True,
                            muted=True,
                            loop=True)

dotted_background = html.Div(id="dotted-background")

#record_title = html.Div([
#    html.Img(src='assets/images/Logo_Museme_white.png',className='logo_header', id="logo_header", width="50", height="50"),
#    html.H1("Let's start !", className="record-title anim-typewriter", id="record-title"),
#    ])


logo_header = html.Div([
                dbc.Col(
                    html.Img(src='assets/images/Logo_Museme_white.png',className='logo_header', id="logo_header", width="50", height="50")), 
                    ]) 



record_title = html.Div([
                    dbc.Row([
                        html.H1(" Museme ", className="record-title anim-typewriter", id="record-title")])])
                        #html.Img(src='assets/images/Logo_Museme_white.png',className='record-title', width="50", height="50", hidden=False, draggable="true")])])

onboarding_layout=html.Div([
                    dbc.Row([
                        html.H1('How to find a music based on the similarity of a music you know ?', className='main_row_onboarding_box'),
                        ]),
                    dbc.Row([
                        html.H2('Step 1: Select the artist from our database', className='row_onboarding_box'),
                        ]),
                    dbc.Row([
                        html.H2('Step 2: Select a title from the artist', className='row_onboarding_box'),
                        ]),
                    dbc.Row([
                        html.H2('Step 3: Discover our results', className='row_onboarding_box'),
                        ]),
                    dbc.Row([
                        html.H2(''),
                        ]),
                    ],className='onboarding-box',id="onboarding-explanation")

cta_onboarding=html.Div([
                dbc.Button("Get it, let's try"),
                    ], className='cta-onboarding', id="onboarding-button")

######################
df_input = functions.load_catalog().sort_values(by=['Artist'])

dropdown_active=html.Div(id='input-dropdown-content')

def display_dropdown_onboarding():
    return html.Div([
                    html.H2('First, select the artist:', className='row_input_box'),
                    dcc.Dropdown(
                        id='artist-dropdown',
                        options=[{'label': i, 'value': i} for i in df_input.Artist.unique()],
                        placeholder='Artist...',
                        className='museme-dropdown'),
                    html.H2('Pick a track:', className='row_input_box'),
                    dcc.Dropdown(
                        id='title-dropdown',
                        placeholder='Track...',
                        className='museme-dropdown'),
                    ], className='input-box')


audio_play = html.Div(id="output-content-upload")

def audio_play_layout(track_info):
    return html.Div([
                        html.P("Your pick", className="track-box-label"),
                        html.Img(src=track_info[2], className="track-coverhq"),
                        html.H5(track_info[0], className="track-artist"),
                        html.H6(track_info[1], className="track-title"),
                        html.Audio(src=track_info[3], controls=True, autoPlay=False,
                                   className="track-audio-controls-bar"),
                ], className="track-audio-player-box")

# def audio_play_layout(track_info):
#     return html.Div([
#                     dbc.Col([
#                         html.Img(src=track_info[2], className="track-coverhq"),
#                             ]),
#                     dbc.Col([
#                         html.H5(track_info[0], className="track-artist"),
#                         html.H6(track_info[1], className="track-title"),
#                         html.Audio(src=track_info[3], controls=True, autoPlay=False, className="track-audio-controls-bar")
#                             ]),
#                 ], className="track-audio-player-box", style={'color':'white'})
        

#NEW: affihcer les 5 reco
recommendation_input= html.Div(id="output-recommendation-upload")

def _recommendation_row(rank, song, artist, preview, cover):
    """Une ligne de recommandation : rang, pochette, textes, lecteur.

    Les 10 lignes etaient ecrites a la main, chacune en dbc.Row de 4 dbc.Col
    de largeur egale : la pochette de 50 px occupait un quart de la colonne
    pendant que les titres longs se repliaient sur trois lignes.
    """
    if pd.isna(cover):
        # 61 morceaux du catalogue n'ont pas de pochette
        vignette = html.Div("♪", className="track-cover-reco track-cover-missing")
    else:
        vignette = html.Img(src=cover, className="track-cover-reco", alt="")

    return html.Div([
        html.Span(f"{rank:02d}", className="reco-rank"),
        vignette,
        html.Div([
            html.Div(song, className="track-title-reco"),
            html.Div(artist, className="track-artist-reco"),
        ], className="reco-text"),
        html.Audio(src=preview, controls=True, autoPlay=False, className="track-audio-reco"),
    ], className="reco-row")


def recommendation_box_layout(df_for_rec):
    lignes = [
        _recommendation_row(rang, r.Song, r.Artist, r.Preview, r.Cover)
        for rang, r in enumerate(df_for_rec.head(10).itertuples(), start=1)
    ]
    return html.Div(
        [html.H2("Check out the most similar tracks:", className="info-recommendation")] + lignes,
        className="track-recommended-player-box")


# La colonne de gauche empile le bloc de selection puis la carte du morceau
# choisi. Les deux etaient positionnes en absolu independamment (top 10% et
# top 40%) et se chevauchaient des que la hauteur de fenetre changeait.
left_panel = html.Div([

    dropdown_active,

    dcc.Loading(
        id="loading-screen",
        type="default",
        parent_className="left-panel-loading",
        children=audio_play,
    ),

], className="left-panel")


# Meme principe a droite : un conteneur qui borne la hauteur et defile, au lieu
# d'un bloc absolu dont les dernieres lignes sortaient de l'ecran.
right_panel = html.Div([recommendation_input], className="right-panel")


layout = html.Div([
    
    #logo_header, 
    logo_header, #display=block (par défaut)

    record_title, #display=block (par défaut)

    background_video, #display=block (par défaut)

    dotted_background, #display=block (par défaut)

    onboarding_layout,

    cta_onboarding,

    left_panel,

    right_panel,
    
], id="main-layout")

