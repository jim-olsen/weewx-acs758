import requests

resp = requests.get('http://10.0.10.128/A0')
if resp.status_code == 200:
	json = resp.json()
	amps = json['A0']
	print(amps)
else:
	raise ApiError('Fetching amps failed with status code ' + resp.status_code)
