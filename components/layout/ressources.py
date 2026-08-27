from dash import html
import dash_bootstrap_components as dbc
from dash import dcc
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import os.path

from app import app 
from components.engine import functions

page_title= html.Div([
                    html.H1('Resources & Credits',style={'textAlign':'center','color':'white'}),
                    ], className='page-title-box')


# ressources_part_lib= html.Div([
#                         html.H1('Librairies', className='title_source', style={"color":"white","fontSize": "1.2em"}),
#                         html.Li([
#                                 html.Span("Dash: ", style={"color": "white", "fontSize": "0.9em"}),
#                                 html.A("https://dash.plot.ly/", href="https://dash.plot.ly/", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
#                                 ]),
#                         html.Li([
#                                 html.Span("Librosa: ", style={"color": "white", "fontSize": "0.9em"}),
#                                 html.A("https://librosa.org/doc/latest/index.html", href="https://librosa.org/doc/latest/index.html", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
#                                 ]),
#                         html.H1('Bibliography', className='title_source', style={"color":"white","fontSize": "1.2em"}),        
#                         ], className='source-lib-box')

ressources_part_lib= html.Div([
                        html.H1('Librairies', className='title_source', style={"color":"white","fontSize": "1.2em"}),
                        html.Li([
                                html.Span("Dash: ", style={"color": "white", "fontSize": "0.9em"}),
                                html.A("https://dash.plot.ly/", href="https://dash.plot.ly/", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li([
                                html.Span("Librosa: ", style={"color": "white", "fontSize": "0.9em"}),
                                html.A("https://librosa.org/doc/latest/index.html", href="https://librosa.org/doc/latest/index.html", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li([
                                html.Span("Spotipy: ", style={"color": "white", "fontSize": "0.9em"}),
                                html.A("https://spotipy.readthedocs.io/en/2.12.0/", href="https://spotipy.readthedocs.io/en/2.12.0/", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li([
                                html.Span("Scikit-learn: ", style={"color": "white", "fontSize": "0.9em"}),
                                html.A("https://sklearn.org/", href="https://sklearn.org/", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li([
                                html.Span("Keras: ", style={"color": "white", "fontSize": "0.9em"}),
                                html.A("https://keras.io/", href="https://keras.io/", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li([
                                html.Span("Pypi: ", style={"color": "white", "fontSize": "0.9em"}),
                                html.A("https://pypi.org/", href="https://pypi.org/", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li([
                                html.Span("Pydub: ", style={"color": "white", "fontSize": "0.9em"}),
                                html.A("http://pydub.com/", href="http://pydub.com/", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li([
                                html.Span("Scipy", style={"color": "white", "fontSize": "0.9em"}),
                                html.A("https://www.scipy.org/docs.html", href="https://www.scipy.org/docs.html", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li([
                                html.Span("Time: ", style={"color": "white", "fontSize": "0.9em"}),
                                html.A("https://docs.python.org/fr/3/library/time.html", href="https://docs.python.org/fr/3/library/time.html", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li([
                                html.Span("Argparse: ", style={"color": "white", "fontSize": "0.9em"}),
                                html.A("https://docs.python.org/3/library/argparse.html", href="https://docs.python.org/3/library/argparse.html", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li([
                                html.Span("Pypianoroll: ", style={"color": "white", "fontSize": "0.9em"}),
                                html.A("https://salu133445.github.io/pypianoroll/", href="https://salu133445.github.io/pypianoroll/", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li([
                                html.Span("Music21: ", style={"color": "white", "fontSize": "0.9em"}),
                                html.A("https://web.mit.edu/music21/doc/", href="https://web.mit.edu/music21/doc/", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li(),
                        html.H1('Bibliography', className='title_source', style={"color":"white","fontSize": "1.2em"}),
                        html.Li([
                                html.Span("Enthought, Brian McFee. Librosa Audio and Music Signal Analysis in Python, 2015: ", style={"color": "white", "fontSize": "0.9em"}),
                                html.A(" link to Youtube", href="https://www.youtube.com/watch?v=MhOdbtPhbLU", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li([
                                html.Span("Wszeborowska, Anna - Processing music on the fly with Python, 2016:", style={"color": "white", "fontSize": "0.9em"}),
                                html.A(" link to Youtube", href="https://www.youtube.com/watch?v=at2NppqIZok", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li([
                                html.Span("Valerio Velardo :", style={"color": "white", "fontSize": "0.9em"}),
                                html.A(" link to Youtube", href="https://www.youtube.com/channel/UCZPFjMe1uRSirmSpznqvJfQ", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li([
                                html.Span("MIR :", style={"color": "white", "fontSize": "0.9em"}),
                                html.A(" link to Website", href="https://musicinformationretrieval.com/", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li([
                                html.Span("Tjoa, Steve : ", style={"color": "white", "fontSize": "0.9em"}),
                                html.A(" link to Github", href="https://github.com/stevetjoa/musicinformationretrieval.com", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li(),
                        html.H1('Credits', className='title_source', style={"color":"white","fontSize": "1.2em"}),
                        html.Li([
                                html.Span("GTZAN Dataset: ", style={"color": "white", "fontSize": "0.9em"}),
                                html.A(" link to Kaggle", href="https://kaggle.com/andradaolteanu/gtzan-dataset-music-genre-classification", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li([
                                html.Span("Olteanu, Andrada « Work w/ Audio Data: Visualise, Classify, Recommend »:", style={"color": "white", "fontSize": "0.9em"}),
                                html.A(" link to Kaggle", href="https://kaggle.com/andradaolteanu/work-w-audio-data-visualise-classify-recommend", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li([
                                html.Span("Chetia, Abhijeet, « Working with Audio Data »: ", style={"color": "white", "fontSize": "0.9em"}),
                                html.A(" link to Kaggle", href="https://kaggle.com/abhijeetchetia/working-with-audio-data", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li([
                                html.Span("Basu, Victor. « Generate Music with Variational AutoEncoder »: ", style={"color": "white", "fontSize": "0.9em"}),
                                html.A(" link to Kaggle", href="https://kaggle.com/basu369victor/generate-music-with-variational-autoencoder", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        html.Li([
                                html.Span("Staebler, Max. Classification: ", style={"color": "white", "fontSize": "0.9em"}),
                                html.A(" link to Github", href="https://github.com/maxistaebler/towardsdatascience", target="_blank", style={"color": "white", "fontSize": "0.9em"}),
                                ]),
                        ], className='source-lib-box')

layout = html.Div([

        page_title,
        
        ressources_part_lib

        ], id="ressources-layout")
