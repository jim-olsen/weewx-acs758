import datetime
import shutil

import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly
import pickle
import requests
import time
import threading
import os
from datetime import datetime
from pymodbus.client.sync import ModbusTcpClient
from dash.dependencies import Input, Output
from os import path

graph_data = {
	'battload': [],
	'time': [],
	'battvoltage': [],
	'battwatts': [],
	'solarwatts': [],
	'targetbattvoltage': [],
	'net_production': []
}
current_data = {}
stats_data = {
	'current_date': datetime.today().date(),
	'total_load_wh': 0,
	'total_net': [],
	'day_load_wh': 0,
	'total_solar_wh': 0,
	'day_solar_wh': 0,
	'day_batt_wh': 0,
	'last_charge_state': 'MPPT',
	'avg_load': 0.0,
	'avg_net': 0.0,
	'avg_solar': 0.0,
	'thirty_days_net': [0] * 30,
	'thirty_days_load': [0] * 30,
	'thirty_days_solar': [0] * 30,
	'thirty_days_batt_wh': [0] * 30
}
# Set this value to the ip of your tristar charge controller
tristar_addr = '10.0.10.10'
# Set this value to the base url of your arduino running the acs758 monitoring
arduino_addr = 'http://10.0.10.31/sensor/'

#
# Our main html style definitions that are shared
#
main_div_style = {
	'backgroundColor': '#111111',
	'color': '#fca503',
	'height': '100%',
	'width': '100%',
	'display': 'flex',
	'flex-direction': 'column'
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
	'height': 270
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
				html.Div(id='graph-div', children=[dcc.Graph(id='live-update-graph')]),
				html.Div(id='stats-div', children=[html.Div(id='live-update-stats')],
						 style={'display': 'none', 'height': 270}),
				html.Div(children=[html.Button('Stats/Graph', id='stats-toggle', n_clicks=0,
											   style={'height': '60px', 'width': '180px'}),
								   html.Div(children=[
									   html.A(html.Button('Refresh', style={'height': '60px', 'width': '80px'}),
											  href='/'),
									   html.Button('Next Graph >>>', id='next-graph', n_clicks=0,
												   style={'height': '60px', 'width': '180px'})])],
						 style={'display': 'flex', 'justify-content': 'space-between'}),
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
# Fetch the data from the arduino and populate our central dictionary of values
#
def update_arduino_values():
	while True:
		try:
			resp = requests.get(arduino_addr + '/A0')
			current_load = 'N/A'
			resp_dict = {}
			if resp.status_code == 200:
				resp_dict = resp.json()
				current_data["battery_load"] = resp_dict['A0']
			else:
				print('Failed to communicate to arduino: ' + str(resp.status_code))
				current_data["battery_load"] = 0
		except Exception as e:
			print('Failed to communicate to arduino: ' + str(e))

		try:
			resp = requests.get(arduino_addr + '/A1')
			current_load = 'N/A'
			resp_dict = {}
			if resp.status_code == 200:
				resp_dict = resp.json()
				current_data["load_amps"] = resp_dict['A1']
			else:
				print('Failed to communicate to arduino: ' + str(resp.status_code))
				current_data["load_amps"] = 0
		except Exception as e:
			print('Failed to communicate to arduino: ' + str(e))
		time.sleep(5)


#
# Update the running stats with the latest data
#
def update_running_stats():
	global stats_data
	while True:
		try:
			if ('load_amps' in current_data) & ('battery_voltage' in current_data):
				stats_data['day_load_wh'] += 0.00139 * (current_data['load_amps'] * current_data['battery_voltage'])
				stats_data['day_solar_wh'] += 0.00139 * current_data['solar_watts']
				stats_data['day_batt_wh'] += 0.00139 * current_data['battery_load'] * current_data['battery_voltage']
				stats_data['total_load_wh'] += 0.00139 * (current_data['load_amps'] * current_data['battery_voltage'])
				stats_data['total_solar_wh'] += 0.00139 * current_data['solar_watts']
				if stats_data['current_date'] != datetime.today().date():
					print('Start of new day : ' + str(stats_data['current_date']) + ' ---> ' + str(datetime.today().date()))
					stats_data['current_date'] = datetime.today().date()
					stats_data['thirty_days_batt_wh'].pop(0)
					stats_data['thirty_days_batt_wh'].append(stats_data['day_batt_wh'])

					stats_data['thirty_days_net'].pop(0)
					stats_data['thirty_days_net'].append(stats_data['day_solar_wh'] - stats_data['day_load_wh'])
					num_valid_entries = 0.0
					avg_sum = 0.0
					for val in stats_data['thirty_days_net']:
						if val != 0:
							avg_sum += val
							num_valid_entries += 1
					if num_valid_entries > 0:
						stats_data['avg_net'] = avg_sum / num_valid_entries

					stats_data['thirty_days_load'].pop(0)
					stats_data['thirty_days_load'].append(stats_data['day_load_wh'])
					num_valid_entries = 0.0
					avg_sum = 0.0
					for val in stats_data['thirty_days_load']:
						if val != 0:
							avg_sum += val
							num_valid_entries += 1
					if num_valid_entries > 0:
						stats_data['avg_load'] = avg_sum / num_valid_entries

					stats_data['thirty_days_solar'].pop(0)
					stats_data['thirty_days_solar'].append(stats_data['day_solar_wh'])
					num_valid_entries = 0.0
					avg_sum = 0.0
					for val in stats_data['thirty_days_solar']:
						if val != 0:
							avg_sum += val
							num_valid_entries += 1
					if num_valid_entries > 0:
						stats_data['avg_solar'] = avg_sum / num_valid_entries

					stats_data['total_net'].append(stats_data['day_solar_wh'] - stats_data['day_load_wh'])
					stats_data['day_load_wh'] = 0
					stats_data['day_solar_wh'] = 0
					stats_data['day_batt_wh'] = 0

				stats_data['last_charge_state'] = current_data['charge_state']
			# persist the latest into a file to handle restarts
			with open('monitor_stats_data.pkl.tmp', 'wb') as f:
				pickle.dump(stats_data, f)
			shutil.move(os.path.join(os.getcwd(), 'monitor_stats_data.pkl.tmp'), os.path.join(os.getcwd(), 'monitor_stats_data.pkl'))
			time.sleep(5)
		except Exception as e:
			print('Failure in updating stats: ' + str(e))


#
# Update the values from the tristar modbus protocol in the values dictionary
#
def update_tristar_values():
	while True:
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
				current_data["battery_voltage"] = float(rr.registers[24]) * voltage_scaling_factor * 2 ** (-15)
				current_data["battery_sense_voltage"] = float(rr.registers[26]) * voltage_scaling_factor * 2 ** (-15)
				current_data["battery_voltage_slow"] = float(rr.registers[38]) * voltage_scaling_factor * 2 ** (-15)
				current_data["battery_daily_minimum_voltage"] = float(
					rr.registers[64]) * voltage_scaling_factor * 2 ** (-15)
				current_data["battery_daily_maximum_voltage"] = float(
					rr.registers[65]) * voltage_scaling_factor * 2 ** (-15)
				current_data["target_regulation_voltage"] = float(rr.registers[51]) * voltage_scaling_factor * 2 ** (
					-15)
				current_data["array_voltage"] = float(rr.registers[27]) * voltage_scaling_factor * 2 ** (-15)
				# Current Related Statistics
				current_data["array_charge_current"] = float(rr.registers[29]) * amperage_scaling_factor * 2 ** (-15)
				current_data["battery_charge_current"] = float(rr.registers[28]) * amperage_scaling_factor * 2 ** (-15)
				current_data["battery_charge_current_slow"] = float(rr.registers[39]) * amperage_scaling_factor * 2 ** (
					-15)
				# Wattage Related Statistics
				current_data["input_power"] = float(
					rr.registers[59]) * voltage_scaling_factor * amperage_scaling_factor * 2 ** (-17)
				current_data["solar_watts"] = float(
					rr.registers[58]) * voltage_scaling_factor * amperage_scaling_factor * 2 ** (-17)
				# Temperature Statistics
				current_data["heatsink_temperature"] = rr.registers[35]
				current_data["battery_temperature"] = rr.registers[36]
				# Misc Statistics
				charge_states = ["START", "NIGHT_CHECK", "DISCONNECT", "NIGHT", "FAULT", "MPPT", "ABSORPTION", "FLOAT",
								 "EQUALIZE", "SLAVE"]
				current_data["charge_state"] = charge_states[rr.registers[50]]
				current_data["seconds_in_absorption_daily"] = rr.registers[77]
				current_data["seconds_in_float_daily"] = rr.registers[79]
				current_data["seconds_in_equalization_daily"] = rr.registers[78]
				modbus_client.close()
		except Exception as e:
			print("Failed to connect to tristar modbus")
			modbus_client.close()
		time.sleep(5)


#
# Update the graph values in the background
#
def update_graph_values():
	while True:
		try:
			global graph_data
			graph_data['time'].append(datetime.now())
			graph_data['battload'].append(current_data["battery_load"])
			graph_data['battvoltage'].append(current_data["battery_voltage"])
			graph_data['battwatts'].append(current_data["battery_voltage"] * current_data["battery_load"])
			# At night this value plummets to zero and screws up the graph, so let's follow the voltage
			# for night time mode
			if current_data["target_regulation_voltage"] == 0:
				graph_data['targetbattvoltage'].append(current_data["battery_voltage"])
			else:
				graph_data['targetbattvoltage'].append(current_data["target_regulation_voltage"])
			graph_data['solarwatts'].append(current_data["solar_watts"])
			graph_data['net_production'].append(stats_data['day_solar_wh'] - stats_data['day_load_wh'])

			# If we have more than a days worth of graph data, start rotating out the old data
			while len(graph_data['time']) > 2880:
				graph_data['time'].pop(0)
				graph_data['battload'].pop(0)
				graph_data['battvoltage'].pop(0)
				graph_data['battwatts'].pop(0)
				graph_data['solarwatts'].pop(0)
				graph_data['targetbattvoltage'].pop(0)
				graph_data['net_production'].pop(0)

			# persist the latest into a file to handle restarts
			with open('monitor_data.pkl.tmp', 'wb') as f:
				pickle.dump(graph_data, f)
			shutil.move(os.path.join(os.getcwd(), 'monitor_data.pkl.tmp'), os.path.join(os.getcwd(), 'monitor_data.pkl'))
		except Exception as e:
			print("Failed to update graph statistics: " + str(e))
		time.sleep(60)


#
# Update the live text elements associated with long running statistics
@app.callback(Output('live-update-stats', 'children'), [Input('text-interval-component', 'n_intervals')])
def update_stats_metrics(n):
	table_rows = []
	td_style = {'border': '1px solid #fca503', 'text-align': 'center', 'font-size': '30px', 'font-family': 'cursive'}

	table_rows.append(html.Tr([
		html.Td(style=td_style, children="Today Usage"),
		html.Td(style=td_style, children='{0:.2f} WH'.format(stats_data['day_load_wh'])),
		html.Td(style=td_style, children="Avg Usage"),
		html.Td(style=td_style, children='{0:.2f} WH'.format(stats_data['avg_load']))]))
	table_rows.append(html.Tr([
		html.Td(style=td_style, children="Today Solar"),
		html.Td(style=td_style, children='{0:.2f} WH'.format(stats_data['day_solar_wh'])),
		html.Td(style=td_style, children="Avg Solar"),
		html.Td(style=td_style, children='{0:.2f} WH'.format(stats_data['avg_solar']))]))
	table_rows.append(html.Tr([
		html.Td(style=td_style, children="Today Net"),
		html.Td(style=td_style, children='{0:.2f} WH'.format(stats_data['day_solar_wh'] - stats_data['day_load_wh'])),
		html.Td(style=td_style, children="Avg Net"),
		html.Td(style=td_style, children='{0:.2f} WH'.format(stats_data['avg_net']))]))
	table_rows.append(html.Tr([
		html.Td(style=td_style, children="Yesterday Net"),
		html.Td(style=td_style, children='{0:.2f} WH'.format(stats_data['thirty_days_net'][29])),
		html.Td(style=td_style, children="Yesterday Use"),
		html.Td(style=td_style, children='{0:.2f} WH'.format(stats_data['thirty_days_load'][29]))]))
	table_rows.append(html.Tr([
		html.Td(style=td_style, children="Today Batt Use"),
		html.Td(style=td_style, children='{0:.2f} WH'.format(stats_data['day_batt_wh'])),
		html.Td(style=td_style, children="Five Day Net"),
		html.Td(style=td_style, children='{0:.2f} WH'.format((stats_data['day_batt_wh']
															 + stats_data['thirty_days_batt_wh'][29]
															 + stats_data['thirty_days_batt_wh'][28]
															 + stats_data['thirty_days_batt_wh'][27]
															 + stats_data['thirty_days_batt_wh'][26]) * -1))]))

	return html.Table(style={'width': '100%', 'border': '1px solid #fca503'}, children=table_rows)


#
# update the text elements displaying the live data point
#
@app.callback(Output('live-update-text', 'children'), [Input('text-interval-component', 'n_intervals')])
def update_text_metrics(n):
	table_elements = []
	header_row = []
	td_style = {'border': '1px solid #fca503', 'text-align': 'center', 'font-size': '30px', 'font-family': 'cursive'}

	# table_elements.append(html.Td(style=td_style, children='{0:.2f} A'.format(battery_load)))
	# header_row.append(html.Th(style=td_style, children='Batt (A)'))
	table_elements.append(
		html.Td(style=td_style, children='{0:.2f}'.format(current_data["load_amps"] * current_data["battery_voltage"])))
	header_row.append(html.Th(style=td_style, children='Load (W)'))
	table_elements.append(html.Td(style=td_style, children='{0:.2f}'.format(current_data["battery_voltage"])))
	header_row.append(html.Th(style=td_style, children='Batt (V)'))
	table_elements.append(
		html.Td(style=td_style,
				children='{0:0.0f}'.format(current_data["battery_voltage"] * current_data["battery_load"])))
	header_row.append(html.Th(style=td_style, children='Batt (W)'))
	table_elements.append(html.Td(style=td_style, children='{0:0.0f}'.format(current_data["solar_watts"])))
	header_row.append(html.Th(style=td_style, children='Solar (W)'))
	table_elements.append(html.Td(style=td_style, children=current_data["charge_state"]))
	header_row.append(html.Th(style=td_style, children='Mode'))

	return html.Table(style={'width': '100%', 'border': '1px solid #fca503'},
					  children=[html.Tr(header_row), html.Tr(table_elements)])


#
# Create the actual graph object, also keeping in mind the currently selected graph that we want to display
#
def create_graph(current_graph):
	fig = plotly.tools.make_subplots(rows=2, cols=1, vertical_spacing=0.2)
	fig['layout'] = graphStyle
	fig['layout']['margin'] = {'l': 30, 'r': 10, 'b': 50, 't': 10}
	fig['layout']['legend'] = {'x': 0, 'y': 1, 'xanchor': 'right'}
	if current_graph == 1:
		fig.append_trace(
			{'x': graph_data['time'], 'y': graph_data['battload'], 'name': 'Load (A)', 'mode': 'lines',
			 'type': 'scatter', 'marker': {'color': '#fca503'}, 'line_shape': 'spline'}, 1, 1)
		fig['layout']['title'] = {'text': 'Batt (A)', 'xanchor': 'center', 'yanchor': 'bottom', 'x': 0.5, 'y': 0,
								  'font': {'color': '#fca503', 'size': 40}}
	if current_graph == 0:
		fig.append_trace(
			{'x': graph_data['time'], 'y': graph_data['battvoltage'], 'name': 'Batt (V)', 'mode': 'lines',
			 'type': 'scatter', 'marker': {'color': '#fca503'}, 'line_shape': 'spline'}, 1, 1)
		fig.append_trace(
			{'x': graph_data['time'], 'y': graph_data['targetbattvoltage'], 'name': 'Target (V)', 'mode': 'lines',
			 'type': 'scatter', 'marker': {'color': '#26f0ec'}, 'line_shape': 'spline'}, 1, 1)
		fig['layout']['title'] = {'text': 'Batt (V)', 'xanchor': 'center', 'yanchor': 'bottom', 'x': 0.5, 'y': 0,
								  'font': {'color': '#fca503', 'size': 40}}
	if current_graph == 2:
		fig.append_trace(
			{'x': graph_data['time'], 'y': graph_data['battwatts'], 'name': 'Batt (W)', 'mode': 'lines',
			 'type': 'scatter', 'marker': {'color': '#fca503'}, 'line_shape': 'spline'}, 1, 1)
		fig['layout']['title'] = {'text': 'Batt (W)', 'xanchor': 'center', 'yanchor': 'bottom', 'x': 0.5, 'y': 0,
								  'font': {'color': '#fca503', 'size': 40}}
	if current_graph == 3:
		fig.append_trace(
			{'x': graph_data['time'], 'y': graph_data['solarwatts'], 'name': 'Solar (W)', 'mode': 'lines',
			 'type': 'scatter', 'marker': {'color': '#fca503'}, 'line_shape': 'spline'}, 1, 1)
		fig['layout']['title'] = {'text': 'Solar (W)', 'xanchor': 'center', 'yanchor': 'bottom', 'x': 0.5, 'y': 0,
								  'font': {'color': '#fca503', 'size': 40}}
	if current_graph == 4:
		fig.append_trace(
			{'x': graph_data['time'], 'y': graph_data['battwatts'], 'name': 'Batt (W)', 'mode': 'lines',
			 'type': 'scatter', 'marker': {'color': '#eb1717'}, 'line_shape': 'spline'}, 1, 1)
		fig.append_trace(
			{'x': graph_data['time'], 'y': graph_data['solarwatts'], 'name': 'Solar (W)', 'mode': 'lines',
			 'type': 'scatter', 'marker': {'color': '#fbff19'}, 'line_shape': 'spline'}, 1, 1)
		fig['layout']['title'] = {'text': 'Batt and Solar (W)', 'xanchor': 'center', 'yanchor': 'bottom', 'x': 0.5,
								  'y': 0, 'font': {'color': '#fca503', 'size': 40}}
	if current_graph == 5:
		fig.append_trace(
			{'x': graph_data['time'], 'y': graph_data['net_production'], 'name': 'Net WH', 'mode': 'lines',
			 'type': 'scatter', 'marker': {'color': '#fca503'}, 'line_shape': 'spline'}, 1, 1)
		fig['layout']['title'] = {'text': 'Net WH', 'xanchor': 'center', 'yanchor': 'bottom', 'x': 0.5, 'y': 0,
								  'font': {'color': '#fca503', 'size': 40}}

	return fig


#
# Toggle the stats display on or off dependent on the number of clicks.  This is paired with the graph div to implement
# toggling between the two displays.
#
@app.callback(Output('stats-div', 'style'), [Input('stats-toggle', 'n_clicks')])
def toggle_stats_div(n_clicks):
	if n_clicks % 2 == 1:
		return {'display': 'block'}
	else:
		return {'display': 'none'}


#
# Toggle the graph display on or off dependent on the number of clicks.  This is paired with the stats div to implement
# toggling between the two displays.
#
@app.callback(Output('graph-div', 'style'), [Input('stats-toggle', 'n_clicks')])
def toggle_graph_div(n_clicks):
	if n_clicks % 2 == 1:
		return {'display': 'none'}
	else:
		return {'display': 'block'}


#
# Our callback for both the next graph button, as well as the interval.  Dash only allows one callback per output.  In
# this case, we want to adjust the graph based on both of these items, so we check to see which input triggered it and
# update the current graph if staying the same, and adjust the currently selected graph if it is in fact the next graph button
#
@app.callback(Output('live-update-graph', 'figure'),
			  [Input('graph-interval-component', 'n_intervals'), Input('next-graph', 'n_clicks')])
def update_graph_live(n, n_clicks):
	current_graph = n_clicks % 6

	return create_graph(current_graph)


#
# Copy the graph data into place, initializing all arrays to the length indicated by the time array.  This protects
# against empty or missing values from getting things out of whack
#
def copy_graph_data(loaded_graph_data):
	graph_length = 0
	if 'time' in loaded_graph_data:
		graph_length = len(loaded_graph_data['time'])
	if graph_length > 0:
		graph_data['time'] = [0] * graph_length
		if 'time' in loaded_graph_data:
			for i in range(len(loaded_graph_data['time'])):
				graph_data['time'][i] = loaded_graph_data['time'][i]
		graph_data['battload'] = [0] * graph_length
		if 'battload' in loaded_graph_data:
			for i in range(len(loaded_graph_data['battload'])):
				graph_data['battload'].append(loaded_graph_data['battload'][i])
				graph_data['battload'].pop(0)
		graph_data['battvoltage'] = [23] * graph_length
		if 'battvoltage' in loaded_graph_data:
			for i in range(len(loaded_graph_data['battvoltage'])):
				graph_data['battvoltage'].append(loaded_graph_data['battvoltage'][i])
				graph_data['battvoltage'].pop(0)
		graph_data['battwatts'] = [0] * graph_length
		if 'battwatts' in loaded_graph_data:
			for i in range(len(loaded_graph_data['battwatts'])):
				graph_data['battwatts'].append(loaded_graph_data['battwatts'][i])
				graph_data['battwatts'].pop(0)
		graph_data['solarwatts'] = [0] * graph_length
		if 'solarwatts' in loaded_graph_data:
			for i in range(len(loaded_graph_data['solarwatts'])):
				graph_data['solarwatts'].append(loaded_graph_data['solarwatts'][i])
				graph_data['solarwatts'].pop(0)
		graph_data['targetbattvoltage'] = [23] * graph_length
		if 'targetbattvoltage' in loaded_graph_data:
			for i in range(len(loaded_graph_data['targetbattvoltage'])):
				graph_data['targetbattvoltage'].append(loaded_graph_data['targetbattvoltage'][i])
				graph_data['targetbattvoltage'].pop(0)
		graph_data['net_production'] = [0] * graph_length
		if 'net_production' in loaded_graph_data:
			for i in range(len(loaded_graph_data['net_production'])):
				graph_data['net_production'].append(loaded_graph_data['net_production'][i])
				graph_data['net_production'].pop(0)


def main():
	global graph_data
	global stats_data
	if path.exists('monitor_data.pkl'):
		try:
			with open('monitor_data.pkl', 'rb') as f:
				# Load into a temp variable so if it fails we stick with initial values
				print("loading graph data from pkl file")
				loaded_graph_data = pickle.loads(f.read())
				copy_graph_data(loaded_graph_data)
		except Exception as e:
			print("Failed to load monitor pkl data: " + str(e))
	if path.exists('monitor_stats_data.pkl'):
		try:
			with open('monitor_stats_data.pkl', 'rb') as f:
				# Load into a temp variale so if it fails we stick with the initial values
				print("Loading stats data from pkl file")
				load_stats_data = pickle.loads(f.read())
				for key, value in load_stats_data.items():
					stats_data[key] = value
		except Exception as e:
			print("Failed to load stats monitor pkl data: " + str(e))
	arduino_thread = threading.Thread(target=update_arduino_values, args=())
	arduino_thread.daemon = True
	arduino_thread.start()
	tristar_thread = threading.Thread(target=update_tristar_values, args=())
	tristar_thread.daemon = True
	tristar_thread.start()
	stats_thread = threading.Thread(target=update_running_stats, args=())
	stats_thread.daemon = True
	stats_thread.start()
	graph_thread = threading.Thread(target=update_graph_values, args=())
	graph_thread.daemon = True
	graph_thread.start()
	app.run_server(debug=False, host='0.0.0.0')


if __name__ == '__main__':
	main()
