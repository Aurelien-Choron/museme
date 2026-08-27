#from dash import Dash
import dash
import dash_bootstrap_components as dbc






app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    prevent_initial_callbacks=True,
    title="Museme",
    update_title="Museme · …",
)
server = app.server
"""
app.config.suppress_callback_exceptions = True

app.layout = html.Div([
    
    dcc.Location(id="url"),
    
    menu_dropdown,
    
    content

])

"""