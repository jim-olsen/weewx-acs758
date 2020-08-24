import datetime
import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly
import requests
from dash.dependencies import Input, Output

main_div_style = {
	'backgroundColor': '#111111',
	'color': '#fca503',
	'height': '100vh'
}

divStyle = {
	'backgroundColor': '#111111',
	'color': '#fca503'
}

graphStyle = {
	'plot_bgcolor': '#111111',
	'paper_bgcolor': '#111111',
	'font': {
		'color': '#fca503'
	}
}

app = dash.Dash(__name__)
app.layout = html.Div(
	style = divStyle,
	children = [
	html.Div(
		style = main_div_style,
		children = [
		html.H2('Cabin Electric Load'),
		html.Div(id='live-update-text'),
		dcc.Graph(id='live-update-graph'),
		dcc.Interval(
			id='text-interval-component',
			interval=5000,  # in milliseconds
			n_intervals=0
		),
		dcc.Interval(
			id='graph-interval-component',
			interval=60000,  # in milliseconds
			n_intervals=0
			)
		])]
)


@app.callback(Output('live-update-text', 'children'), [Input('text-interval-component', 'n_intervals')])
def update_text_metrics(n):

	resp = requests.get('http://10.0.10.128/A0')
	current_load = 'N/A'
	if resp.status_code == 200:
		resp_dict = resp.json()
		print('Received: ')
		print(resp_dict)
		current_load = '{0:.2f}'.format(resp_dict['A0'])
	else:
		print('Failed to communicate to arduino: ' + resp.status_code)

	return html.Span('Current Load: ' + current_load)

@app.callback(Output('live-update-graph', 'figure'), [Input('graph-interval-component', 'n_intervals')])
def update_graph_live(n):
	fig = plotly.tools.make_subplots(rows=2, cols=1, vertical_spacing=0.2)
	resp = requests.get('http://10.0.10.128/A0')
	current_load = 'N/A'
	if resp.status_code == 200:
		resp_dict = resp.json()
		print('Received: ')
		print(resp_dict)
		graphData['time'].append(datetime.datetime.now())
		graphData['cabinload'].append(resp_dict['A0'])
		if (len(graphData) > 1440):
			graphData['time'].pop(0)
			graphData['cabinload'].pop(0)

		fig['layout'] = graphStyle;
		fig['layout']['margin'] = {'l': 30, 'r': 10, 'b': 30, 't': 10}
		fig['layout']['legend'] = {'x': 0, 'y': 1, 'xanchor': 'left'}
		fig.append_trace({'x': graphData['time'], 'y': graphData['cabinload'], 'name': 'Load', 'mode': 'lines+markers',
					  'type': 'scatter'}, 1, 1)
	else:
		print('Failed to communicate to arduino: ' + resp.status_code)
	return fig


def main():
	global graphData
	graphData = {'cabinload': [], 'time': []}
	app.run_server(debug=True, host='0.0.0.0')

if __name__ == '__main__':
	main()
