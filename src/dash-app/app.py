import datetime
import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly
import requests
from pymodbus.client.sync import ModbusTcpClient
from dash.dependencies import Input, Output

current_graph = 0
graph_data = {}
# Set this value to the ip of your tristar charge controller
tristar_addr = '10.0.10.10'
# Set this value to the base url of your arduino running the acs758 monitoring
arduino_addr = 'http://10.0.10.33'

#
# Our main html style definitions that are shared
#
main_div_style = {
	'backgroundColor': '#111111',
	'color': '#fca503',
	'height': '100%',
	'width': '100%'
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
	},
	'height': 280
}

# Initialize the dash app and the main html page
app = dash.Dash('Cabin Energy Monitor')
app.layout = html.Div(
	style=divStyle,
	children=[
		html.Div(
			style=main_div_style,
			children=[
				html.Div(id='live-update-text'),
				html.Div(id='live-update-button'),
				dcc.Graph(id='live-update-graph'),
				html.Button('Next Graph >>>', id='next-graph', n_clicks=0, style={'height': '60px', 'width': '240px'}),
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


#
# Fetch the data from both the tristar charge controller and the arduino running the current sensor and update
# the text elements displaying the live dta point
#
@app.callback(Output('live-update-text', 'children'), [Input('text-interval-component', 'n_intervals')])
def update_text_metrics(n):
	table_elements = []
	header_row = []
	td_style = {'border': '1px solid #fca503', 'text-align': 'center', 'font-size': '30px', 'font-family': 'cursive'}

	# Make a rest call to the arduino to fetch the current amperage value on the battery sensor
	resp = requests.get(arduino_addr + '/A0')
	current_load = 'N/A'
	resp_dict = {}
	if resp.status_code == 200:
		resp_dict = resp.json()
		current_load = '{0:.2f} A'.format(resp_dict['A0'])
		table_elements.append(html.Td(style=td_style, children=current_load))
		header_row.append(html.Th(style=td_style, children='Battery Load'))
	else:
		print('Failed to communicate to arduino: ' + str(resp.status_code))
		resp_dict['A0'] = 0

	# Connect directly to the modbus interface on the tristar charge controller to get the current information about
	# the state of the solar array and battery charging
	modbus_client = ModbusTcpClient(tristar_addr, port=502)
	try:
		modbus_client.connect()
		rr = modbus_client.read_holding_registers(0, 91, unit=1)
		if rr is None:
			modbus_client.close()
			print("Failed to connect and read from tristar modbus")
		else:
			voltage_scaling_factor = (float(rr.registers[0]) + (float(rr.registers[1]) / 100))
			amperage_scaling_factor = (float(rr.registers[2]) + (float(rr.registers[3]) / 100))

			# Voltage Related Statistics
			battery_voltage = float(rr.registers[24]) * voltage_scaling_factor * 2 ** (-15)
			table_elements.append(html.Td(style=td_style, children='{0:.2f} V'.format(battery_voltage)))
			header_row.append(html.Th(style=td_style, children='Batt Voltage'))
			table_elements.append(
				html.Td(style=td_style, children='{0:0.0f} W'.format(battery_voltage * resp_dict['A0'])))
			header_row.append(html.Th(style=td_style, children='Batt Watts'))
			battery_sense_voltage = float(rr.registers[26]) * voltage_scaling_factor * 2 ** (-15)
			battery_voltage_slow = float(rr.registers[38]) * voltage_scaling_factor * 2 ** (-15)
			battery_daily_minimum_voltage = float(rr.registers[64]) * voltage_scaling_factor * 2 ** (-15)
			battery_daily_maximum_voltage = float(rr.registers[65]) * voltage_scaling_factor * 2 ** (-15)
			target_regulation_voltage = float(rr.registers[51]) * voltage_scaling_factor * 2 ** (-15)
			array_voltage = float(rr.registers[27]) * voltage_scaling_factor * 2 ** (-15)
			# Current Related Statistics
			array_charge_current = float(rr.registers[29]) * amperage_scaling_factor * 2 ** (-15)
			battery_charge_current = float(rr.registers[28]) * amperage_scaling_factor * 2 ** (-15)
			battery_charge_current_slow = float(rr.registers[39]) * amperage_scaling_factor * 2 ** (-15)
			# Wattage Related Statistics
			input_power = float(rr.registers[59]) * voltage_scaling_factor * amperage_scaling_factor * 2 ** (-17)
			output_power = float(rr.registers[58]) * voltage_scaling_factor * amperage_scaling_factor * 2 ** (-17)
			table_elements.append(html.Td(style=td_style, children='{0:0.0f} W'.format(output_power)))
			header_row.append(html.Th(style=td_style, children='Solar Watts'))
			# Temperature Statistics
			heatsink_temperature = rr.registers[35]
			battery_temperature = rr.registers[36]
			# Misc Statistics
			charge_states = ["START", "NIGHT_CHECK", "DISCONNECT", "NIGHT", "FAULT", "MPPT", "ABSORPTION", "FLOAT", "EQUALIZE", "SLAVE"]
			charge_state = charge_states[rr.registers[50]]
			table_elements.append(html.Td(style=td_style, children=charge_state))
			header_row.append(html.Th(style=td_style, children='Charge State'))
			seconds_in_absorption_daily = rr.registers[77]
			seconds_in_float_daily = rr.registers[79]
			seconds_in_equalization_daily = rr.registers[78]
			modbus_client.close()

	except Exception as e:
		print("Failed to connect to tristar modbus")
		modbus_client.close()

	return html.Table(style={'width': '100%', 'border': '1px solid #fca503'}, children=[html.Tr(header_row), html.Tr(table_elements)])


#
# Create the actual graph object, also keeping in mind the currently selected graph that we want to display
#
def create_graph():
	global current_graph
	fig = plotly.tools.make_subplots(rows=2, cols=1, vertical_spacing=0.2)
	fig['layout'] = graphStyle
	fig['layout']['margin'] = {'l': 30, 'r': 10, 'b': 30, 't': 10}
	fig['layout']['legend'] = {'x': 0, 'y': 1, 'xanchor': 'right'}
	if current_graph == 0:
		fig.append_trace(
			{'x': graph_data['time'], 'y': graph_data['battload'], 'name': 'Batt Load', 'mode': 'lines',
				'type': 'scatter', 'marker': {'color': '#fca503'}, 'line_shape': 'spline'}, 1, 1)
		fig['layout']['title'] = {'text': 'Batt Load', 'xanchor': 'right', 'yanchor': 'bottom', 'x': 0.5, 'y': 0}
	if current_graph == 1:
		fig.append_trace(
			{'x': graph_data['time'], 'y': graph_data['battvoltage'], 'name': 'Batt Voltage', 'mode': 'lines',
				'type': 'scatter', 'marker': {'color': '#fca503'}}, 1, 1)
		fig['layout']['title'] = {'text': 'Batt Voltage', 'xanchor': 'right', 'yanchor': 'bottom', 'x': 0.5, 'y': 0}
	if current_graph == 2:
		fig.append_trace(
			{'x': graph_data['time'], 'y': graph_data['battwatts'], 'name': 'Batt Watts', 'mode': 'lines',
				'type': 'scatter', 'marker': {'color': '#fca503'}}, 1, 1)
		fig['layout']['title'] = {'text': 'Batt Watts', 'xanchor': 'right', 'yanchor': 'bottom', 'x': 0.5, 'y': 0}
	if current_graph == 3:
		fig.append_trace(
			{'x': graph_data['time'], 'y': graph_data['solarwatts'], 'name': 'Solar Watts', 'mode': 'lines',
			 'type': 'scatter', 'marker': {'color': '#fca503'}}, 1, 1)
		fig['layout']['title'] = {'text': 'Solar Watts', 'xanchor': 'right', 'yanchor': 'bottom', 'x': 0.5, 'y': 0}
	if current_graph == 4:
		fig.append_trace(
			{'x': graph_data['time'], 'y': graph_data['battwatts'], 'name': 'Batt Watts', 'mode': 'lines',
			 'type': 'scatter', 'marker': {'color': '#eb1717'}}, 1, 1)
		fig.append_trace(
			{'x': graph_data['time'], 'y': graph_data['solarwatts'], 'name': 'Solar Watts', 'mode': 'lines',
			 'type': 'scatter', 'marker': {'color': '#fbff19'}}, 1, 1)
		fig['layout']['title'] = {'text': 'Batt and Solar Watts', 'xanchor': 'right', 'yanchor': 'bottom', 'x': 0.5, 'y': 0}

	return fig


#
# Our callback for both the next graph button, as well as the interval.  Dash only allows one callback per output.  In
# this case, we want to adjust the graph based on both of these items, so we check to see which input triggered it and
# fetch new data if it is the interval, and adjust the currently selected graph if it is in fact the next graph button
#
@app.callback(Output('live-update-graph', 'figure'),
				[Input('graph-interval-component', 'n_intervals'), Input('next-graph', 'n_clicks')])
def update_graph_live(n, n_clicks):
	global current_graph
	global graph_data

	# If this is triggered by the interval, update the data
	if dash.callback_context.triggered[0]['prop_id'].split('.')[0] != 'next-graph':
		resp = requests.get(arduino_addr + '/A0')
		if resp.status_code == 200:
			resp_dict = resp.json()
			graph_data['time'].append(datetime.datetime.now())
			graph_data['battload'].append(resp_dict['A0'])
			# Connect directly to the modbus interface on the tristar charge controller to get the current information about
			# the state of the solar array and battery charging
			modbus_client = ModbusTcpClient(tristar_addr, port=502)
			try:
				modbus_client.connect()
				rr = modbus_client.read_holding_registers(0, 91, unit=1)
				if rr is None:
					modbus_client.close()
					print("Failed to connect and read from tristar modbus")
				else:
					voltage_scaling_factor = (float(rr.registers[0]) + (float(rr.registers[1]) / 100))
					amperage_scaling_factor = (float(rr.registers[2]) + (float(rr.registers[3]) / 100))
					battery_voltage = float(rr.registers[24]) * voltage_scaling_factor * 2 ** (-15)
					graph_data['battvoltage'].append(battery_voltage)
					graph_data['battwatts'].append(battery_voltage * resp_dict['A0'])
					output_power = float(rr.registers[58]) * voltage_scaling_factor * amperage_scaling_factor * 2 ** (
						-17)
					graph_data['solarwatts'].append(output_power)

					# If we have more than a days worth of graph data, start rotating out the old data
					if len(graph_data) > 1440:
						graph_data['time'].pop(0)
						graph_data['battload'].pop(0)
						graph_data['battvoltage'].pop(0)
						graph_data['battwatts'].pop(0)
						graph_data['solarwatts'].pop(0)
					modbus_client.close()
			except Exception as e:
				print("Failed to connect to tristar modbus")
				modbus_client.close()
		else:
			print('Failed to communicate to arduino: ' + resp.status_code)
	else:
		# The next graph button was pressed, so just update the selected graph and redraw
		current_graph = (current_graph + 1) % 5

	return create_graph()


def main():
	global graph_data
	graph_data = {'battload': [], 'time': [], 'battvoltage': [], 'battwatts': [], 'solarwatts': []}
	app.run_server(debug=True, host='0.0.0.0')


if __name__ == '__main__':
	main()
